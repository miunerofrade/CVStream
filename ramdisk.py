import os
import ctypes

def setup_ramdisk(letter="R:", size="1G"):
    """使用 Windows 原生 ShellExecuteW 触发 UAC，无视环境限制"""
    if os.path.exists(f"{letter}\\"):
        return True, "已存在"

     
    params = f'-a -s {size} -m {letter} -p "/fs:ntfs /q /y"'
    
     
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "imdisk", params, None, 0)
    
     
    if ret > 32:
        return True, "提权弹窗已发送"
    else:
        return False, f"API 调用失败，错误码: {ret}"

def remove_ramdisk(letter="R:"):
    if not os.path.exists(f"{letter}\\"):
        return True, "已卸载"
        
     
    params = f'-D -m {letter}'
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "imdisk", params, None, 0)
    
    if ret > 32:
        return True, "卸载请求已发送"
    else:
        return False, f"卸载失败，错误码: {ret}"