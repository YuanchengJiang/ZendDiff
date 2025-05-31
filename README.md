## ZendDiff — A Differential Testing Framework for PHP Interpreter

### What is ZendDiff?

ZendDiff is a fully automated differential testing framework designed to uncover **logic bugs** in the PHP interpreter by comparing its behavior under Just-In-Time (JIT) and non-JIT execution modes. While prior fuzzers focus mainly on memory errors or crash-triggered issues, ZendDiff excels at detecting **silent correctness bugs** that escape traditional oracles.

### Why ZendDiff?

The PHP interpreter, powering over 70% of websites worldwide, is critical to the web ecosystem. With the introduction of **JIT compilation** in PHP 8+, an alternative implementation of language semantics is available—opening the door to **differential testing**. ZendDiff seizes this opportunity to uncover inconsistencies between JIT and non-JIT executions.

ZendDiff has already identified **35 previously unknown logic bugs**, 25 of which have been fixed and 5 confirmed by PHP developers. It significantly **outperforms the official PHP test suite** in both code coverage and the number of executed Zend opcodes.

### How Does ZendDiff Work?

ZendDiff combines three core techniques to efficiently reveal logic bugs:

* **Program State Probing**
  We instrument test cases to capture detailed runtime states, enabling comparisons beyond printed outputs or exit codes.

* **JIT-Aware Program Mutation**
  We carefully mutate PHP programs to trigger diverse JIT behaviors (e.g., by varying `opcache.jit` modes, hot thresholds, or input types), maximizing semantic coverage.

* **Dual Verification**
  Each test is run twice under both JIT and non-JIT modes. The results are compared pairwise for consistency, and additional verification steps are used to filter out non-deterministic behaviors.

ZendDiff builds upon **FlowFusion**, leveraging `.phpt` test files from the official PHP suite. These seed programs are fused and mutated to generate thousands of unique and semantically rich test cases that efficiently cover different execution paths.

---

### Instructions

Follow these steps to fuzz the latest commit of `php-src` using ZendDiff in a Docker container.

1. **Clone ZendDiff & Prepare**
   Inside the container:

   ```bash
   cd ZendDiff
   ./prepare.sh
   ```

   > ℹ️ *ZendDiff builds on FlowFusion’s infrastructure. The `prepare.sh` script configures the environment and fetches necessary PHP sources.*

2. **Start Testing**
   Use `tmux` to maintain long-running sessions:

   ```bash
   tmux new-session -s zenddiff 'bash'
   ```

   Then run ZendDiff:

   ```bash
   python3 main.py
   ```

4. **View Found Bugs**
   After fuzzing:

   ```bash
   find ./bugs -name "diff"
   ```

---

### Results

ZendDiff has demonstrated its effectiveness in real-world testing:

* Identified 35 logic bugs in PHP
* 25 already fixed by maintainers
* Surpassed official test suite in coverage and depth
* Praised and adopted by PHP core developers