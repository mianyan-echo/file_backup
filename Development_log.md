# 目录级备份开发日志

从2020.02.15开始，记录每次更新的更新内容、更新前的漏洞以及学到的东西

***

## 2020.02.15

***

本来预计将现在零散的函数整理成一个类，方便后期的GUI调用。

但在尝试备份/var目录时，在`/var/lib/samba/private/msg.sock`下的文件全部报错`OSError: [Errno 6] No such device or address`，因为之前出现过open损坏的软连接报错的问题，所以去看了一下`/var/lib/samba/private/msg.sock`下的文件，发现全部为s类型的socket文件，是linux的伪文件。这是代码里一直被忽略的问题，所以这次更改主要整理了代码里备份时的逻辑，**添加`get_type`函数来判断原文件的类型**。

在修改后测试的时候又发现了一个很蠢的问题，虽然之前有注意判断文件是否为软连接，但并没有注意目录是否为软连接，也完全没有保证复制后目录的mode与原目录一致，导致一些特殊的目录属性与原目录不同，所以**改写了创建目录的部分，并且让程序不再复制软连接目录里的文件**。

关于这里涉及到了一个备份软件的偏向，我选择了让程序尽可能的还原目录本来的样子，而不是更多的内容，所以**如果要备份的目录为一个软连接的话，程序也仅仅只将软连接备份过去**。

经过测试不管是在USB3.0的移动机械硬盘还是SATA固态硬盘，**python使用`get_type`(或者说`os.lstat`)读磁盘的matedata都比新建立一个空线程开销小得多**，另外两种硬盘环境下`get_type`函数开销没有差太多。所以将判断文件是否需要复制的步骤放在新建复制线程外可以减小线程开销，但是如果不是像/dev这种有很多伪文件的目录，反而会降低程序的并行能力而降低性能。

测试代码为:

```python
import time
from threading import Thread
import os


def nothing():
    pass


def get_type(src):
    try:
        st = os.lstat(src)
    except (OSError, AttributeError):
        return ' '
    return os.st.filemode(st.st_mode)[0]


path = '/etc'
dirlist = os.listdir(path)
lendir = len(dirlist)
os.chdir(path)


a = time.time()

for i in dirlist:
    get_type(i)

b = time.time()
print('读{}个matedata粗略估用时{}'.format(lendir, b-a))

# Test to create some new threads
a = time.time()

for i in range(lendir):
    Thread(target=nothing).start()

b = time.time()
print('建立{}个线程粗略估用时{}'.format(lendir, b-a))

```

