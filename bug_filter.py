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
    if "php_strip_whitespace(__FILE__)" in php or "set_error_handler" in php or 'Fatal error: The "yield" expression can only be used inside a function' in diff \
       or "refcount(" in diff or 'opcache_compile_file(__FILE__)' in php or 'opcache_is_script_cached(__FILE__)' in php or 'var_dump( gmdate($format, $timestamp) );' in php \
       or 'gmmktime' in php or '--Seconds since Unix Epoch--' in diff or "opcache_get_status()['jit']" in php or '+ noArray' in diff or 'float(1.0000000000000002)' in diff \
       or '$config["directives"]["opcache.enable' in php or 'opcache_get_status()' in php or 'JIT is disabled' in diff or 'time' in php or 'on line 241' in diff or 'Server is not running' in diff:
        continue
    else:
        print(each)
        print(diff)
        input()
