import os,hashlib

from utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader , TextLoader

def get_file_md5_hex(file_path:str): # 计算文件md5 十六进制字符串

    if not os.path.exists(file_path):
        logger.error(f"[md5计算]文件{file_path}不存在")
        return

    if not os.path.isfile(file_path):
        logger.error(f"[md5计算]文件{file_path}不是文件")
        return

    md5_obj = hashlib.md5()

    chunk_size = 4096 # 每次读取4K，避免内存溢出

    try:
        with open(file_path, "rb") as f:  # 必须二进制方式打开文件
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)
                logger.debug(f"[md5计算]计算文件{file_path}的md5中...")

                md5_hex = md5_obj.hexdigest()
                return md5_hex # 文件md5值

    except Exception as e:
        logger.error(f"[md5计算]计算文件{file_path}的md5时出错:{e}")
        return None


def listdir_with_allowed_type(dir_path:str, allowed_types:tuple[str]): # 列出指定目录下的所有文件，并筛选出指定类型的文件

    files = []
    if not os.path.isdir(dir_path):
        logger.error(f"[listdir_with_allowed_type]{dir_path}不是文件夹")
        return allowed_types

    for f in os.listdir(dir_path):
        if f.endswith(allowed_types):
            files.append(os.path.join(dir_path, f))

    return tuple(files)

def pdf_loader(file_path:str , passwd = None)-> list[Document]:
    return PyPDFLoader(file_path, passwd).load()


def txt_loader(file_path:str) -> list[Document]:
    return TextLoader(file_path, encoding='utf-8').load()
