"""
程序备份时所用内存与算hash时单次读的块大小有关，与线程最大数有关
"""
import os
import json
import shutil
import hashlib
from threading import Thread, Semaphore
import filecmp


def get_time():
    from datetime import datetime
    times = str(datetime.now()).split()
    return times[0] + '_' + times[1]


def get_hash(file_name: str, hash_type: str = 'md5') -> str:
    """
    生成文件的hsah码，可选hash的类型：
    'md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512',
    'blake2b', 'blake2s',
    'sha3_224', 'sha3_256', 'sha3_384', 'sha3_512'
    :param file_name:文件的名字
    :param hash_type:想选择的hash类型
    :return:返回文件对应的hash
    """
    # 获得对应类型的编码器
    hash_mode = getattr(hashlib, hash_type)
    mode = hash_mode()
    with open(file_name, 'rb') as file_obj:
        while True:
            data = file_obj.read(8192)
            if not data:
                break

            mode.update(data)
    return mode.hexdigest()


def get_path(path):
    # 翻译环境变量
    path = os.path.expandvars(path)
    # 翻译'～'等
    path = os.path.expanduser(path)
    # 返回绝对路径
    return os.path.abspath(path)


def copy_symlink(src, dst):
    os.symlink(os.readlink(src), dst)


def _create_file_md5(src, dst, _new_md5_list, _all_md5_list, _max_thread_num):
    # print("\rcp:{}".format(src), end='', flush=True)
    # 判断文件名是否为软连接
    if os.path.islink(src):
        # 如果是，再建一个软连接
        copy_symlink(src, dst)
        # os.symlink(os.readlink(source_file_path), target_file_path)
    else:
        # 不是,就正常的算md5
        file_md5 = get_hash(src)
        if file_md5 not in _all_md5_list:
            # Thread(target=shutil.copy2, args=[source_file_path, target_file_path]).start()
            shutil.copy2(src, dst)
            _new_md5_list.update({file_md5: dst})
        else:
            os.link(_all_md5_list[file_md5], dst)
    _max_thread_num.release()


def _create_file_md5pp(src, dst, _last_dst, _new_md5_list, _all_md5_list, _max_thread_num):
    # print("\rcp:{}".format(src), end='', flush=True)
    # 判断文件名是否为软连接
    if os.path.islink(src):
        # 如果是，再建一个软连接
        copy_symlink(src, dst)
        # os.symlink(os.readlink(source_file_path), target_file_path)
    # 这里经过测试证明，and时会先算and前的，如果为false，就不会算and后的bool值了
    # a = False
    # a and b
    # out: False
    # b and a
    # out: NameError: name 'd' is not defined
    elif os.path.exists(_last_dst) and filecmp.cmp(src, _last_dst):
        os.link(_last_dst, dst)
    else:
        # 不是,就正常的算md5
        file_md5 = get_hash(src)
        if file_md5 not in _all_md5_list:
            # Thread(target=shutil.copy2, args=[source_file_path, target_file_path]).start()
            shutil.copy2(src, dst)
            _new_md5_list.update({file_md5: dst})
        else:
            os.link(_all_md5_list[file_md5], dst)
    _max_thread_num.release()


def backup_core(src: str, dst: str, max_thread_num=256):
    # 限制最大复制线程数
    max_thread_num = Semaphore(max_thread_num)
    source_path = get_path(src)
    target_path = get_path(dst)
    time = get_time()

    if not os.path.exists(target_path):
        os.makedirs(target_path)

    if os.path.exists(target_path + '/md5_list.json'):
        if os.path.getsize(target_path + '/md5_list.json') != 0:
            # 加载json文件
            with open(target_path + '/md5_list.json') as fp:
                final_md5_list = json.load(fp)
                # 找出上一次的备份文件夹路径，方便对比文件是否修改
                if len(final_md5_list) > 1:
                    last_target_path = target_path + '/' + list(final_md5_list.keys())[-2]
                elif len(final_md5_list) == 1:
                    last_target_path = target_path + '/' + 'base'
                else:
                    last_target_path = None
            time_tag = time
        else:
            time_tag = 'base'
            final_md5_list = {'base': {}}
            last_target_path = None
    else:
        # 如果不存在md5_list.json则创建
        open(target_path + '/md5_list.json', 'w').close()
        time_tag = 'base'
        final_md5_list = {'base': {}}
        last_target_path = None

    target_path = target_path + '/' + time_tag
    os.makedirs(target_path)
    os.chdir(target_path)

    # 得到全部最新的md5码
    all_md5_list = {}
    for dir_key in final_md5_list:
        all_md5_list.update(final_md5_list[dir_key])

    new_md5_list = {}
    walk = os.walk(source_path)

    if last_target_path is None:
        for item in walk:
            for folder in item[1]:
                target_folder_path = target_path + item[0][len(source_path):] + '/' + folder
                if not os.path.exists(target_folder_path):
                    os.makedirs(target_folder_path)

            for file in item[2]:
                # 得到原文件绝对路径
                source_file_path = item[0] + '/' + file
                # 得到目的文件绝对路径
                target_file_path = target_path + item[0][len(source_path):] + '/' + file

                max_thread_num.acquire()
                Thread(target=_create_file_md5, args=[source_file_path,
                                                      target_file_path,
                                                      new_md5_list,
                                                      all_md5_list,
                                                      max_thread_num]).start()

    else:
        for item in walk:
            for folder in item[1]:
                target_folder_path = target_path + item[0][len(source_path):] + '/' + folder
                if not os.path.exists(target_folder_path):
                    os.makedirs(target_folder_path)

            for file in item[2]:
                # 得到原文件绝对路径
                source_file_path = item[0] + '/' + file
                # 得到目的文件绝对路径
                target_file_path = target_path + item[0][len(source_path):] + '/' + file
                last_target_file_path = last_target_path + item[0][len(source_path):] + '/' + file

                max_thread_num.acquire()
                Thread(target=_create_file_md5pp, args=[source_file_path,
                                                        target_file_path,
                                                        last_target_file_path,
                                                        new_md5_list,
                                                        all_md5_list,
                                                        max_thread_num]).start()

    final_md5_list.update({time_tag: new_md5_list})
    md5_list_str = json.dumps(final_md5_list, sort_keys=True, indent=4)

    with open(target_path[:-len(time_tag)] + 'md5_list.json', 'w') as fp:
        fp.write(md5_list_str)


if __name__ == '__main__':
    backup_core('~/anaconda3', '/media/mianyan/linux_backup/anaconda3')
