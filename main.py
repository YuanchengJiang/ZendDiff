import os
import random
import glob
import time
import datetime
import shutil
import threading
from fuse import Fusion
from mutator import Mutator

# Class for handling PHP fuzzing process
class PHPFuzz:
    """
    PHPFuzz: A comprehensive PHP fuzzing framework with differential testing capabilities.
    
    This class implements a fuzzing strategy for PHP that combines various techniques:
    - Mutation-based fuzzing: modifies existing test cases
    - API fuzzing: targets PHP's API surface
    - INI configuration fuzzing: tests different PHP configurations
    - Fusion-based testing: combines multiple test cases together
    
    The framework implements a multi-level verification strategy to reduce false positives
    through differential testing between JIT and non-JIT execution modes.
    """

    def __init__(self):
        """
        Initialize the PHPFuzz class with various configurations and settings.
        """
        # Fuzzing strategy configuration flags
        self.mutation = True  # Enable mutation-based fuzzing
        self.apifuzz = True   # Enable API surface fuzzing
        self.ini = True       # Enable INI configuration fuzzing
        self.fusion = True    # Enable test case fusion

        # Coverage feedback (disabled by default due to performance impact)
        self.coverage = False
        
        # File system paths
        self.test_root = "/home/phpfuzz/WorkSpace/flowfusion"  # Root directory for testing
        self.php_root = f"{self.test_root}/php-src"            # PHP source code directory
        self.fused = f"{self.php_root}/tests/fused"            # Directory for fused test cases
        self.mutated = f"{self.php_root}/tests/mutated"        # Directory for mutated test cases
        self.bug_folder = f"{self.test_root}/bugs/"            # Directory to store found bugs
        self.log_path = "/tmp/test.log"                        # Log path for test execution

        # Initialize environment and directory structure
        self.patch_run_test()      # Patch PHP's test runner to avoid conflicts
        self.backup_initials()     # Backup original PHP configuration files
        self.check_target_exist()  # Verify PHP source exists
        self.init_fused_folder()   # Initialize directory for fused tests
        self.init_bug_folder()     # Initialize directory for bugs
        self.init_phpt_path()      # Initialize PHPT test paths
        self.moveout_builtin_phpts()  # Remove built-in PHPTs to avoid conflicts

        # Statistics tracking
        self.total_count = 1           # Total number of tests executed
        self.syntax_error_count = 0    # Count of syntax errors encountered
        self.stopping_test_num = -1    # Stop after this many tests (-1 means infinite)     

        # Differential testing configuration
        self.verification = 2  # Level of verification (higher = more checks to reduce false positives)

    #
    # ENVIRONMENT SETUP METHODS
    #
    
    def backup_initials(self):
        """
        Backup original PHP configuration files before fuzzing.
        
        Note: We don't backup the latest run-tests.php as it may have updates.
        Instead, we keep a known working version in the backup folder.
        """
        os.system(f"cp {self.php_root}/Makefile {self.test_root}/backup/")
        os.system(f"cp {self.php_root}/libtool {self.test_root}/backup/")

    def patch_run_test(self):
        """
        Patch PHP's run-tests.php script to disable conflict checking and improve stability.
        
        The patches:
        1. Disable test conflict detection
        2. Prevent worker process termination
        3. Skip certain file iteration code paths
        """
        os.chdir(self.php_root)
        # Disable conflict checking by adding 'continue' in the conflict loop
        os.system("sed -i 's/foreach (\$fileConflictsWith\[\$file\] as \$conflictKey) {/foreach (\$fileConflictsWith\[\$file\] as \$conflictKey) { continue;/g' ./run-tests.php")
        # Comment out process termination commands
        os.system("sed -i 's/proc_terminate(\$workerProcs\[\$i\]);/\/\/proc_terminate(\$workerProcs\[\$i\]);/' ./run-tests.php")
        os.system("sed -i 's/unset(\$workerProcs\[\$i\], \$workerSocks\[\$i\]);/\/\/unset(\$workerProcs\[\$i\], \$workerSocks\[\$i\]);/' ./run-tests.php")
        # Add continue to skip over file iteration
        os.system("sed -i 's/foreach (\$test_files as \$i => \$file) {/foreach (\$test_files as \$i => \$file) { continue;/' ./run-tests.php")
        os.chdir(self.test_root)

    def moveout_builtin_phpts(self):
        """
        Remove all built-in PHPT test files to avoid conflicts with fuzzer-generated tests.
        """
        os.system(f"find {self.php_root} -name '*.phpt' | xargs rm 2>/dev/null")

    def init_phpt_path(self):
        """
        Initialize the path to seed PHPT files by finding all PHPTs in the seed directory.
        """
        os.system(f'find {self.test_root}/phpt_seeds/ -name "*.phpt" > {self.test_root}/testpaths')

    def init_bug_folder(self):
        """
        Create the bug folder if it doesn't exist to store discovered bugs.
        """
        if not os.path.exists(self.bug_folder):
            os.makedirs(self.bug_folder)

    def check_target_exist(self):
        """
        Check if the target PHP build directory exists, exit if not found.
        """
        if not os.path.exists(self.php_root):
            print(f"{self.php_root} not found..")
            exit(-1)

    def init_fused_folder(self):
        """
        Initialize the directory for fused test cases with necessary dependencies.
        
        This method:
        1. Creates the fused tests directory if it doesn't exist
        2. Copies dependencies from phpt_deps folder
        3. Restores original PHP configuration files
        4. Adds empty directories to git to preserve structure
        5. Commits changes to save the initial state
        """
        if not os.path.exists(self.fused):
            os.system(f"mkdir {self.fused}")

            # Check for dependencies in the phpt_deps folder
            dependency = f"{self.test_root}/phpt_deps"
            if not os.path.exists(dependency):
                print(f"{dependency} not found..")
                exit(-1)

            # Restore dependencies and initial configuration
            os.system(f"cp -R {dependency}/* {self.fused}")
            os.system(f"cp {self.test_root}/backup/run-tests.php {self.php_root}/")
            os.system(f"cp {self.test_root}/backup/Makefile {self.php_root}/")
            os.system(f"cp {self.test_root}/backup/libtool {self.php_root}/")
            
            # Create placeholder files in empty directories to preserve git structure
            os.system(f"cd {self.php_root}/tests/fused/ && find . -type d -empty -exec touch {{}}/.gitkeep \;")
            
            # Save the initial state to git
            os.system(f"cd {self.php_root} && git add ./tests/fused/ && git add -f ./tests/fused/* && git config --global user.email '0599jiangyc@gmail.com' && git config --global user.name 'fuzzsave' && git commit -m 'fuzzsave'")
            print("fused inited! git status saved!")

    def check_build(self):
        """
        Check if the PHP CLI binary exists (indicating a successful build).
        """
        return os.path.exists(f"{self.php_root}/sapi/cli/php")

    #
    # BUG ANALYSIS METHODS
    #

    def diff_two_strings(self, string1, string2):
        """
        Generate a diff between two strings to highlight differences.
        
        Args:
            string1: First string to compare
            string2: Second string to compare
            
        Returns:
            String containing the formatted diff output
        """
        # Limit string sizes to prevent processing extremely large outputs
        if len(string1) > 59999 or len(string2) > 59999:
            return "too long to diff; please check manually"
            
        import difflib
        differ = difflib.Differ()
        try:
            # Use the compare method to get the differences
            diff = differ.compare(string1.splitlines(), string2.splitlines())
        except Exception as e:
            print("error in diff strings")
            print(str(e))
            return "gg"
            
        # Convert the diff to a formatted string
        diff_list = list(diff)
        diffs = ""
        for line in diff_list:
            diffs += line + '\n'
        return diffs

    def buglog(self, bugid, normal_out_path, jit_out_path, diff):
        """
        Log a discovered bug by copying relevant files and saving the diff.
        
        Args:
            bugid: Unique ID for the bug
            normal_out_path: Path to normal (non-JIT) output file
            jit_out_path: Path to JIT output file
            diff: Diff string between the outputs
        """
        # Create a directory for this bug
        os.makedirs(f"{self.bug_folder}/{bugid}")
        
        # Copy all related files (preserving original extensions)
        os.system(f"cp {normal_out_path.split('.')[0]}.* {self.bug_folder}/{bugid}/")
        os.system(f"cp {jit_out_path.split('.')[0]}.* {self.bug_folder}/{bugid}/")
        
        # Save the diff to a file
        f = open(f"{self.bug_folder}/{bugid}/diff", "w")
        f.write(diff)
        f.close()

    #
    # DIFFERENTIAL TESTING IMPLEMENTATION
    #

    def zendiff_parse_log(self):
        """
        Differential testing oracle to find bugs by comparing JIT and non-JIT output.
        
        This implements a multi-level verification strategy:
        - Check1: Compare standard JIT vs non-JIT output
        - Check2: Compare with a second execution to rule out non-determinism
        - Check3: Compare with a third execution for further verification
        
        The method counts passing and failing test cases at each verification level
        and logs potential bugs to the bug folder.
        """
        # Initialize counters for various verification levels
        self.check1_count = 0
        self.check2_count = 0
        self.check3_count = 0
        self.check1_pass_count = 0
        self.check2_pass_count = 0
        self.check3_pass_count = 0
        self.check1_fail_count = 0
        self.check2_fail_count = 0
        self.check3_fail_count = 0
        self.verification = 2
        self.check = 0  # count of test cases checked by oracle
        self.check_oprec = []
        self.opcode = False
        self.opcode1 = set()
        self.opcode2 = set()
        self.opcode3 = set()
        self.opcode_rec = []
        
        # Get all output files from fused test directory
        allfiles = os.listdir(f"{self.php_root}/tests/fused/")
        outputs = []
        for each_file in allfiles:
            if each_file.endswith(".out"):
                outputs.append(each_file)
                
        # Initialize bug ID counter
        bugid = len(os.listdir(self.bug_folder)) + 1
        print("test case number:", len(outputs) / 4)
        
        # Local counters for this batch
        check1_count = 0
        check2_count = 0
        check3_count = 0
        check1_pass_count = 0
        check2_pass_count = 0
        check3_pass_count = 0
        check1_fail_count = 0
        check2_fail_count = 0
        check3_fail_count = 0
        incomplete_count = 0
        all_outputs = ""
        
        # Process each output file
        for each_output in outputs:
            if self.verification > 0:
                # Find JIT output files (but not the verification ones)
                if "_jit" in each_output and "_jit_check" not in each_output:
                    normal_out = each_output.replace("_jit", "")
                    jit_out = each_output
                    
                    # First verification level: Check if JIT and non-JIT outputs differ
                    if normal_out in outputs:
                        check1_count += 1
                        normal_out_path = f"{self.php_root}/tests/fused/{normal_out}"
                        jit_out_path = f"{self.php_root}/tests/fused/{jit_out}"

                        # Read non-JIT output
                        f = open(normal_out_path, 'r', encoding="iso_8859_1")
                        _normal_out = f.read()
                        f.close()

                        # Read JIT output
                        f = open(jit_out_path, 'r', encoding="iso_8859_1")
                        _jit_out = f.read()
                        f.close()

                        # Compare outputs
                        if _normal_out != _jit_out:
                            check1_fail_count += 1
                            
                            # Second verification level: Check if the difference is reproducible
                            if self.verification > 1:
                                normal_check = each_output.replace("_jit", "_check")
                                jit_check = each_output.replace("_jit", "_jit_check")
                                
                                if normal_check in outputs and jit_check in outputs:
                                    check2_count += 1
                                    normal_check_path = f"{self.php_root}/tests/fused/{normal_check}"
                                    jit_check_path = f"{self.php_root}/tests/fused/{jit_check}"

                                    # Read verification outputs
                                    f = open(normal_check_path, 'r', encoding="iso_8859_1")
                                    _normal_check = f.read().replace("_check.php", ".php")
                                    f.close()

                                    f = open(jit_check_path, 'r', encoding="iso_8859_1")
                                    _jit_check = f.read().replace("_jit_check.php", ".php")
                                    f.close()
                                    
                                    # If outputs differ from first run, it might be non-deterministic behavior
                                    if _normal_out != _normal_check or _jit_out != _jit_check:
                                        check2_pass_count += 1
                                        continue
                                    else:
                                        # Outputs match first run, proceed to third verification
                                        check2_fail_count += 1
                                        if self.verification > 2:
                                            normal_check_ = each_output.replace("_jit", "_check_")
                                            jit_check_ = each_output.replace("_jit", "_jit_check_")
                                            
                                            if normal_check_ in outputs and jit_check_ in outputs:
                                                check3_count += 1
                                                normal_check__path = f"{self.php_root}/tests/fused/{normal_check_}"
                                                jit_check__path = f"{self.php_root}/tests/fused/{jit_check_}"

                                                # Read third verification outputs
                                                f = open(normal_check__path, 'r', encoding="iso_8859_1")
                                                _normal_check_ = f.read().replace("_check_.php", ".php")
                                                f.close()

                                                f = open(jit_check__path, 'r', encoding="iso_8859_1")
                                                _jit_check_ = f.read().replace("_jit_check_.php", ".php")
                                                f.close()
                                                
                                                # Final verification check
                                                if _normal_out != _normal_check_ or _jit_out != _jit_check_:
                                                    check3_pass_count += 1
                                                    continue
                                                else:
                                                    # All verification levels confirm the bug
                                                    check3_fail_count += 1
                                            else:
                                                incomplete_count += 1
                                                continue
                                else:
                                    incomplete_count += 1
                                    continue
                                    
                            # Log the bug with a diff of the outputs
                            diff = self.diff_two_strings(_normal_out, _jit_out)
                            self.buglog(bugid, normal_out_path, jit_out_path, diff)
                            bugid += 1
                        else:
                            # Outputs match, no bug
                            check1_pass_count += 1

        # Print verification statistics for this batch
        print("check1[total,pass,fail]:", check1_count, check1_pass_count, check1_fail_count)
        print("check2[total,pass,fail]:", check2_count, check2_pass_count, check2_fail_count)
        print("check3[total,pass,fail]:", check3_count, check3_pass_count, check3_fail_count)
        print("incomplete_count", incomplete_count)
        
        # Update cumulative statistics
        self.check1_count += check1_count
        self.check2_count += check2_count
        self.check3_count += check3_count
        self.check1_pass_count += check1_pass_count
        self.check2_pass_count += check2_pass_count
        self.check3_pass_count += check3_pass_count
        self.check1_fail_count += check1_fail_count
        self.check2_fail_count += check2_fail_count
        self.check3_fail_count += check3_fail_count
        
        # Print cumulative statistics
        print("total check1[total,pass,fail]:", self.check1_count, self.check1_pass_count, self.check1_fail_count)
        print("total check2[total,pass,fail]:", self.check2_count, self.check2_pass_count, self.check2_fail_count)
        print("total check3[total,pass,fail]:", self.check3_count, self.check3_pass_count, self.check3_fail_count)

    # Parse the test log for failed tests and possible bugs
    def parse_log(self):
        """
        Parse PHP test logs to identify crashes and other severe issues.
        
        This looks for crashes, sanitizer reports, and core dumps in test outputs,
        then copies relevant files to the bug folder.
        """
        known_crash_sites = ["leak"]  # Known issues to ignore

        # Read test log
        with open(self.log_path, "r") as f:
            logs = f.read().strip("\n").split("\n")

        next_log_id = len(os.listdir(self.bug_folder)) + 1
        for eachlog in logs:
            # Only process failed fusion tests
            if "FAIL" not in eachlog or "tests/fused" not in eachlog:
                continue
                
            # Extract test case path
            casepath = self.php_root + "/" + eachlog.split("[")[-1].split("]")[0].replace(".phpt", "")
            stdouterr = f"{casepath}.out"
            
            if not os.path.exists(stdouterr):
                continue
                
            # Read test output
            with open(stdouterr, "r", encoding="iso_8859_1") as f:
                content = f.read()
                self.total_count += 1
                
                # Track syntax errors
                if "Parse error" in content:
                    self.syntax_error_count += 1
                    
                # Skip memory leaks by default
                if "leaked in" in content:
                    continue
                    
                # Look for crashes (sanitizer reports or core dumps)
                if "Sanitizer" in content or "(core dumped)" in content:
                    # Create bug directory and move relevant files
                    os.makedirs(f"{self.bug_folder}/{next_log_id}")
                    shutil.move(f"{casepath}.out", f"{self.bug_folder}/{next_log_id}/test.out")
                    shutil.move(f"{casepath}.php", f"{self.bug_folder}/{next_log_id}/test.php")
                    shutil.move(f"{casepath}.phpt", f"{self.bug_folder}/{next_log_id}/test.phpt")
                    shutil.move(f"{casepath}.sh", f"{self.bug_folder}/{next_log_id}/test.sh")
                    next_log_id += 1

    #
    # UTILITY METHODS
    #

    def clean(self):
        """
        Clean up test artifacts by removing temporary files from the fused test directory.
        """
        os.system(f"find {self.fused} -type f -name '*.log' -o -name '*.out' -o -name '*.diff' -o -name '*.sh' -o -name '*.php' -o -name '*.phpt' | xargs rm 2>/dev/null")

    def collect_cov(self, fuzztime):
        """
        Collect code coverage information using gcovr.
        
        Args:
            fuzztime: Current fuzzing time (used in output filename)
        """
        def run_coverage_collection():
            # Change to PHP source directory
            os.chdir(self.php_root)
            
            # Run gcovr to collect coverage, excluding third-party libraries
            cmd = f"gcovr -sr . -o /tmp/gcovr-{fuzztime}.xml --xml --exclude-directories 'ext/date/lib$$' -e 'ext/bcmath/libbcmath/.*' -e 'ext/date/lib/.*' -e 'ext/fileinfo/libmagic/.*' -e 'ext/gd/libgd/.*' -e 'ext/hash/sha3/.*' -e 'ext/mbstring/libmbfl/.*' -e 'ext/pcre/pcre2lib/.*' > /dev/null"
            os.system(cmd)
            
            # Return to test root directory
            os.chdir(self.test_root)
            
            # Parse coverage percentage from XML output
            with open(f"/tmp/gcovr-{fuzztime}.xml", "r") as f:
                x = f.read()
            self.coverage = float(x.split('line-rate="')[1].split('"')[0])
            print(f"Coverage: {self.coverage:.2%}")

        # Run coverage collection in a separate thread to avoid blocking
        coverage_thread = threading.Thread(target=run_coverage_collection)
        coverage_thread.start()

    def runtime_log(self, seconds, rounds):
        """
        Display runtime statistics including execution time, bugs found, and throughput.
        
        Args:
            seconds: Total execution time in seconds
            rounds: Number of fuzzing rounds completed
        """
        # Count bugs found
        bugs_found = len(os.listdir(f"{self.test_root}/bugs/"))
        
        # Print statistics
        print(f"\ntime: {int(seconds)} seconds | bugs found: {bugs_found} | tests executed: {self.total_count} | throughput: {self.total_count/seconds} tests per second\n")
        
        # Print coverage if available
        if self.coverage != 0:
            print(f"line code coverage: {self.coverage:.2%}")
            
        # Check if we've reached the stopping condition
        if self.stopping_test_num > 0 and self.total_count > self.stopping_test_num:
            print("stopped")
            exit(0)

    #
    # MAIN FUZZING LOOP
    #

    def main(self):
        """
        Main function to execute the continuous fuzzing process.
        
        This method:
        1. Checks for a valid PHP build
        2. Initializes the fuzzing environment
        3. Runs the main fuzzing loop that generates and executes test cases
        4. Periodically cleans the environment and collects statistics
        """
        # Check for valid PHP build
        if not self.check_build():
            print("php not build")
            exit()

        count = 0
        start = time.time()
        covtime = 60*60  # Collect coverage every hour
        fuzztime = 0
        self.coverage = 0

        fusion_thread = None

        print("Start flowfusion...")

        # Initialize the Fusion engine for test case generation
        phpFusion = Fusion(self.test_root, self.php_root, self.apifuzz, self.ini, self.mutation, self.verification)

        # Main fuzzing loop
        while True:
            count += 1
            
            # Periodically clean the environment and restore configurations
            if count % 10 == 0:
                # Clean the test folder while preserving important directories
                os.system(f"cd {self.test_root} && git clean -fd -e php-src -e phpt_deps -e phpt_seeds -e knowledges -e backup -e bugs -e testpaths")
                os.system(f"cp {self.test_root}/backup/run-tests.php {self.php_root}/")
                os.system(f"cp {self.test_root}/backup/Makefile {self.php_root}/")
                os.system(f"cp {self.test_root}/backup/libtool {self.php_root}/")
                
            # Clean test artifacts
            self.clean()

            # Generate new test cases using Fusion engine
            phpFusion.main()

            # Execute test cases with timeout and parallelism
            os.chdir(self.php_root)
            os.system('timeout 30 make test TEST_PHP_ARGS="-j32 --set-timeout 5 --offline" 2>/dev/null | grep "FAIL" > /tmp/test.log')
            os.chdir(self.test_root)
            
            # Fix permissions and clean up stray processes
            os.system(f"chmod -R 777 {self.test_root} 2>/dev/null")
            os.system("kill -9 `ps aux | grep \"/home/phpfuzz/WorkSpace/flowfusion/php-src/sapi/cli/php\" | grep -v grep | awk '{print $2}'` > /dev/null 2>&1")
            os.system("kill -9 `ps aux | grep \"/home/phpfuzz/WorkSpace/flowfusion/php-src/sapi/phpdbg/phpdbg\" | grep -v grep | awk '{print $2}'` > /dev/null 2>&1")
            
            # Analyze results using differential testing
            self.zendiff_parse_log()

            # Clean up git repository
            os.system(f"cd {self.php_root} && git clean -fd > /dev/null")

            # Collect coverage periodically
            end = time.time()
            timelen = end - start
            if timelen > covtime + fuzztime:
                fuzztime += covtime
                self.collect_cov(fuzztime)

            # Log runtime statistics
            self.runtime_log(timelen, count)

# Initialize and run the fuzzing process
fuzz = PHPFuzz()
fuzz.main()