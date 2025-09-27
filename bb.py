import os

bugs = os.listdir("./bugs")

for each in bugs:
    f = open(f"./bugs/{each}/diff", 'r', encoding = 'iso-8859-1')
    diff = f.read()
    f.close()
    os.system(f"cp ./bugs/{each}/*_jit.php /tmp/test.php")
    f = open(f"/tmp/test.php", 'r', encoding = 'iso-8859-1')
    php = f.read()
    f.close()
    if "php_strip_whitespace(__FILE__)" in php or "set_error_handler" in php or 'Fatal error: The "yield" expression can only be used inside a function' in diff:
        continue
    else:
        print(each)
        print(diff)
        input()
