"""
程序备份时所用内存与算hash时单次读的块大小有关，与线程最大数有关
经过考虑还是选择尽可能的还原要备份的文件的真实面目，是软连接就是软连接，有什么属性就是什么属性，
哪怕要拷贝的最外层文件夹是软连接，也会只当作软连接拷贝
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


def _get_path(path):
    # 翻译环境变量
    path = os.path.expandvars(path)
    # 翻译'～'等
    path = os.path.expanduser(path)
    # 返回绝对路径
    return os.path.abspath(path)


def copy_symlink(src, dst):
    os.symlink(os.readlink(src), dst)


def get_type(src):
    try:
        st = os.lstat(src)
    except (OSError, AttributeError):
        return ' '
    return os.st.filemode(st.st_mode)[0]


class Backup_base:
    def __init__(self, src, dst, files_num_flag=[0], max_thread_num=256):
        if files_num_flag is None:
            files_num_flag = [0]
        target_path = _get_path(dst)

        if not os.path.exists(target_path):
            os.makedirs(target_path)

        self.md5_list_path = target_path + '/md5_list.json'
        self._max_thread_num = Semaphore(max_thread_num)
        self.source_path = _get_path(src)
        self.target_path = target_path
        self.files_num_flag = files_num_flag
        self._time = get_time()
        self._backup_files_dict = {}

    def analysis(self):
        # do something
        return self.files_num_flag

    def backup(self):
        # do something
        pass

    def _create_file_md5(self, src, dst, _new_md5_list, _all_md5_list, _max_thread_num):
        # 定义纯靠md5备份函数
        pass

    def _create_file_md5pp(self, src, dst, _last_dst, _new_md5_list, _all_md5_list, _max_thread_num):
        # 定义靠md5和mtime与size共同备份的函数
        pass


class Linux_backup_core(Backup_base):
    def __init__(self, src, dst, files_num_flag=[0], max_thread_num=256):
        super(Linux_backup_core, self).__init__(src, dst, files_num_flag, max_thread_num)
        if os.path.exists(self.md5_list_path):
            if os.path.getsize(self.md5_list_path) != 0:
                # 加载json文件
                with open(self.md5_list_path) as fp:
                    _final_md5_list = json.load(fp)
                    # 找出上一次的备份文件夹路径，方便对比文件是否修改
                    if len(_final_md5_list) > 1:
                        last_target_path = self.target_path + '/' + list(_final_md5_list.keys())[-2]
                    elif len(_final_md5_list) == 1:
                        last_target_path = self.target_path + '/' + 'base'
                    else:
                        last_target_path = None
                time_tag = self._time
            else:
                time_tag = 'base'
                _final_md5_list = {'base': {}}
                last_target_path = None
        else:
            # 如果不存在md5_list.json则创建
            open(self.md5_list_path, 'w').close()
            time_tag = 'base'
            _final_md5_list = {'base': {}}
            last_target_path = None

        self._final_md5_list = _final_md5_list
        self.last_target_path = last_target_path
        self.target_path = self.target_path + '/' + time_tag
        self._time_tag = time_tag
        os.makedirs(self.target_path)
        os.chdir(self.target_path)

    def analysis(self):
        # 预定义保存要备份的文件的字典
        backup_files_dict = {}
        walk = os.walk(self.source_path)
        for item in walk:
            if get_type(item[0]) == 'l':
                copy_symlink(item[0], self.target_path + item[0][len(self.source_path):])
                continue
            for folder in item[1]:
                source_folder_path = item[0] + '/' + folder
                target_folder_path = self.target_path + item[0][len(self.source_path):] + '/' + folder
                if get_type(source_folder_path) == 'l':
                    copy_symlink(source_folder_path, target_folder_path)
                elif not os.path.exists(target_folder_path):
                    os.makedirs(target_folder_path)
                    os.chmod(target_folder_path, os.stat(source_folder_path).st_mode)

            for file in item[2]:
                # 得到原文件绝对路径
                source_file_path = item[0] + '/' + file
                # 得到目的文件绝对路径
                target_file_path = self.target_path + item[0][len(self.source_path):] + '/' + file
                backup_files_dict.update({source_file_path: target_file_path})

        self._backup_files_dict = backup_files_dict
        self.files_num_flag[0] += len(backup_files_dict)
        return self.files_num_flag

    def backup(self):
        # 得到全部最新的md5码
        all_md5_list = {}
        for dir_key in self._final_md5_list:
            all_md5_list.update(self._final_md5_list[dir_key])

        new_md5_list = {}

        # 将有差异的备份独立出来，先分析晚要备份的文件，再根据情况备份
        if self.last_target_path is None:
            for source_file_path in self._backup_files_dict:
                self._max_thread_num.acquire()
                Thread(target=self._create_file_md5, args=[source_file_path,
                                                           self._backup_files_dict[source_file_path],
                                                           new_md5_list,
                                                           all_md5_list,
                                                           self._max_thread_num]).start()
        else:
            lengh_flag = len(self.target_path)
            for source_file_path in self._backup_files_dict:
                target_file_path = self._backup_files_dict[source_file_path]
                last_target_file_path = self.last_target_path + target_file_path[lengh_flag:]

                self._max_thread_num.acquire()
                Thread(target=self._create_file_md5pp, args=[source_file_path,
                                                             target_file_path,
                                                             last_target_file_path,
                                                             new_md5_list,
                                                             all_md5_list,
                                                             self._max_thread_num]).start()

        self._final_md5_list.update({self._time_tag: new_md5_list})
        md5_list_str = json.dumps(self._final_md5_list, sort_keys=True, indent=4)

        with open(self.target_path[:-len(self._time_tag)] + 'md5_list.json', 'w') as fp:
            fp.write(md5_list_str)

    def _create_file_md5(self, src, dst, _new_md5_list, _all_md5_list, _max_thread_num):
        src_file_type = get_type(src)
        # print("\rcp:{}".format(src), end='', flush=True)
        # 判断文件名是否为软连接
        if src_file_type == 'l':
            # 如果是，再建一个软连接
            copy_symlink(src, dst)
            # os.symlink(os.readlink(source_file_path), target_file_path)
        elif src_file_type == '-':
            # 不是,就正常的算md5
            file_md5 = get_hash(src)
            if file_md5 not in _all_md5_list:
                # Thread(target=shutil.copy2, args=[source_file_path, target_file_path]).start()
                shutil.copy2(src, dst)
                _new_md5_list.update({file_md5: dst})
            else:
                os.link(_all_md5_list[file_md5], dst)
        self.files_num_flag[0] -= 1
        _max_thread_num.release()

    def _create_file_md5pp(self, src, dst, _last_dst, _new_md5_list, _all_md5_list, _max_thread_num):
        src_file_type = get_type(src)
        # print("\rcp:{}".format(src), end='', flush=True)
        # 判断文件名是否为软连接
        if src_file_type == 'l':
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
        elif src_file_type == '-':
            # 不是,就正常的算md5
            file_md5 = get_hash(src)
            if file_md5 not in _all_md5_list:
                # Thread(target=shutil.copy2, args=[source_file_path, target_file_path]).start()
                shutil.copy2(src, dst)
                _new_md5_list.update({file_md5: dst})
            else:
                os.link(_all_md5_list[file_md5], dst)
        self.files_num_flag[0] -= 1
        _max_thread_num.release()


# 方便线程调用
def analysis_file(obj):
    obj.analysis()


def backup_file(obj):
    obj.backup()


if __name__ == '__main__':
    flag = [0]
    core = Linux_backup_core('~/PycharmProjects/test', '/media/mianyan/linux_backup/test', flag)
    analysis_file(core)
    print(flag)
    backup_file(core)
    print(flag)
