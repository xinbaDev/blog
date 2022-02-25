---
title: "一个简单的c程序在linux下所需要的系统调用"
date: 2019-08-20T19:39:11+11:00
summary: 最近了解到了一个叫strace的神器，可以看到程序运行时的系统调用。于是写了个简单程序来做分析。这篇文章主要分析一个简单的c程序（如上）在运行时所需要的系统调用。但是不会深入分析系统调用的具体实现，如果有兴趣可以看我写的另一篇文章《一个系统调用的linux内核(v5.25)实现》, 里面有详细分析setdomainname的系统调用的内核实现。这里主要从更高的层次去分析，程序运行时为什么需要这些系统调用。
draft: false
---

### setdomainname.c

```c=
int main(int argc, char* argv[])
{
    setdomainname("test.com", 100);
}
```

最近了解到了一个叫strace的神器，可以看到程序运行时的系统调用。于是写了个简单程序来做分析。这篇文章主要分析一个简单的c程序（如上）在运行时所需要的系统调用。但是不会深入分析系统调用的具体实现，如果有兴趣可以看我写的另一篇文章《[一个系统调用的linux内核(v5.25)实现](https://hackmd.io/3skVW05ISfmjRVuoDAbDXQ)》, 里面有详细分析setdomainname的系统调用的内核实现。这里主要从更高的层次去分析，程序运行时为什么需要这些系统调用。

### In Ubuntu 16.04 (Debian)

首先 ```gcc setdomainname.c```
然后 ```stace ./a.out```

下面是涉及到的所有系统调用，英文注释基本上都是从[Linux Programmer's Manual](http://man7.org/linux)抓下来的，还有一些stackoverflow上面的解释。

```bash=
# In Linux a new process is created via fork(), which makes a child process
# which is almost identical to the parent process. To create a new process 
# whose program is different than the program of the original process, the
# new child process immediately calls execve(), which is basically the 
# process saying "replace my current program with this other program"
> execve("./a.out", ["./a.out"], [/* 27 vars */]) = 0

# return the current end of the data segment
brk(NULL)                               = 0x1535000
access("/etc/ld.so.nohwcap", F_OK)      = -1 ENOENT (No such file or directory)
access("/etc/ld.so.preload", R_OK)      = -1 ENOENT (No such file or directory)
open("/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3

# return information about a file（/etc/ld.so.cache）, in the buffer
# pointed to by statbuf
fstat(3, {st_mode=S_IFREG|0644, st_size=178504, ...}) = 0

# void *mmap(void *addr, size_t length, int prot, int flags,
# int fd, off_t offset);
# mmap() creates a new mapping in the virtual address space of the
# calling process. The starting address for the new mapping is specified 
# in addr. 
# 
# If addr is NULL, then the kernel chooses the (page-aligned) address
# at which to create the mapping; this is the most portable method of
# creating a new mapping.  
# 
# The prot argument describes the desired memory protection of the
# mapping (and must not conflict with the open mode of the file).
# PROT_EXEC  Pages may be executed.
# PROT_READ  Pages may be read.
# PROT_WRITE Pages may be written.
# PROT_NONE  Pages may not be accessed.
# 
# The flags argument determines whether updates to the mapping are
# visible to other processes mapping the same region, and whether
# updates are carried through to the underlying file.  This behavior is
# determined by including exactly one of the following values in flags:
# 
# MAP_PRIVATE
# Create a private copy-on-write mapping.  Updates to the
# mapping are not visible to other processes mapping the same
# file, and are not carried through to the underlying file.  It
# is unspecified whether changes made to the file after the
# mmap() call are visible in the mapped region.

mmap(NULL, 178504, PROT_READ, MAP_PRIVATE, 3, 0) = 0x7f0fb9f02000
close(3)  = 0

access("/etc/ld.so.nohwcap", F_OK)      = -1 ENOENT (No such file or directory)
open("/lib/x86_64-linux-gnu/libc.so.6", O_RDONLY|O_CLOEXEC) = 3
read(3, "\177ELF\2\1\1\3\0\0\0\0\0\0\0\0\3\0>\0\1\0\0\0P\t\2\0\0\0\0\0"..., 832) = 832
fstat(3, {st_mode=S_IFREG|0755, st_size=1868984, ...}) = 0

# read/write data segment?
mmap(NULL, 4096, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0) = 0x7f0fb9f01000

# read/excute,deny write code segment?
mmap(NULL, 3971488, PROT_READ|PROT_EXEC, MAP_PRIVATE|MAP_DENYWRITE, 3, 0) = 0x7f0fb993f000

# mprotect() changes the access protections for the calling process's
# memory pages containing any part of the address range in the interval
# [addr, addr+len-1]
# Pages may not be accessed
mprotect(0x7f0fb9aff000, 2097152, PROT_NONE) = 0

mmap(0x7f0fb9cff000, 24576, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_FIXED|MAP_DENYWRITE, 3, 0x1c0000) = 0x7f0fb9cff000

mmap(0x7f0fb9d05000, 14752, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_FIXED|MAP_ANONYMOUS, -1, 0) = 0x7f0fb9d05000
close(3)= 0

----------------------------------------------------------------------------

# MAP_ANONYMOUS
# The mapping is not backed by any file; its contents are
# initialized to zero.  The fd argument is ignored; however,
# some implementations require fd to be -1 if MAP_ANONYMOUS (or
# MAP_ANON) is specified, and portable applications should
# ensure this.
mmap(NULL, 4096, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0) = 0x7f0fb9f00000
mmap(NULL, 4096, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0) = 0x7f0fb9eff000

# sets architecture-specific process or thread state
# ARCH_SET_FS（Set the 64-bit base for the FS register to addr）
arch_prctl(ARCH_SET_FS, 0x7f0fb9f00700) = 0

# change PROT_READ|PROT_WRITE to PROT_READ
mprotect(0x7f0fb9cff000, 16384, PROT_READ) = 0

# 0x600000 ！？
mprotect(0x600000, 4096, PROT_READ)     = 0
mprotect(0x7f0fb9f2e000, 4096, PROT_READ) = 0

# The munmap() function shall remove any mappings for those entire
# pages containing any part of the address space of the process
# starting at addr and continuing for len bytes. 
# /etc/ld.so.cache
munmap(0x7f0fb9f02000, 178504)          = 0

setdomainname("test.com\0\0\0\0\1\33\3;4\0\0\0\5\0\0\0\20\376\377\377\200\0\0\0"..., 100) = -1 EINVAL (Invalid argument)
exit_group(0)                           = ?
```

可以看到，在调用setdomainname之前，还调用了其他的系统掉用，他们分别是
1. execve
2. brk
3. access
4. open
5. close
6. fstat
7. mmap
8. mprotect
9. arch_prctl
10. munmap

其中mmap, mprotect反复出现。mmap（以及brk）是内核分配内存的一个重要的系统调用，而mprotect则是设置内存的特性（可读/可写等）。这几个重要的系统调用我以后都会专门分析其内核代码实现。可以看到，在运行setdomainname之前，系统主要工作是将相应所需的文件映射到内存，并设置相关的属性。其中系统读取了两个文件 /etc/ld.so.cache， libc.so.6。[ld](https://linux.die.net/man/1/ld)是动态链接器，而[libc](http://man7.org/linux/man-pages/man7/libc.7.html)这是标准c库, 而setdomainname的定义就是在这个库里面（一个wrapper，会去调用真正的系统调用）。

接下来我们看看在Manjaro里面，相同的c程序在运行时所需要的系统调用。

### In Manjaro (Arch Linux)


```bash=
execve("./a.out", ["./a.out"], 0x7fff77d94e50 /* 58 vars */) = 0
brk(NULL)                               = 0x55653e00a000

arch_prctl(0x3001 /* ARCH_??? */, 0x7ffd252ee5b0) = -1 EINVAL (Invalid argument)

access("/etc/ld.so.preload", R_OK)      = -1 ENOENT (No such file or directory)
openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3
fstat(3, {st_mode=S_IFREG|0644, st_size=222529, ...}) = 0
mmap(NULL, 222529, PROT_READ, MAP_PRIVATE, 3, 0) = 0x7f6735227000
close(3)                                = 0

openat(AT_FDCWD, "/usr/lib/libc.so.6", O_RDONLY|O_CLOEXEC) = 3
read(3, "\177ELF\2\1\1\3\0\0\0\0\0\0\0\0\3\0>\0\1\0\0\0\360o\2\0\0\0\0\0"..., 832) = 832
lseek(3, 64, SEEK_SET)                  = 64
read(3, "\6\0\0\0\4\0\0\0@\0\0\0\0\0\0\0@\0\0\0\0\0\0\0@\0\0\0\0\0\0\0"..., 784) = 784
lseek(3, 848, SEEK_SET)                 = 848
read(3, "\4\0\0\0\20\0\0\0\5\0\0\0GNU\0\2\0\0\300\4\0\0\0\3\0\0\0\0\0\0\0", 32) = 32
lseek(3, 880, SEEK_SET)                 = 880
read(3, "\4\0\0\0\24\0\0\0\3\0\0\0GNU\0\250\257l\201\313(\243{\363\245F\227\v\366B$"..., 68) = 68
fstat(3, {st_mode=S_IFREG|0755, st_size=2133648, ...}) = 0

mmap(NULL, 8192, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0) = 0x7f6735225000

lseek(3, 64, SEEK_SET)                  = 64
read(3, "\6\0\0\0\4\0\0\0@\0\0\0\0\0\0\0@\0\0\0\0\0\0\0@\0\0\0\0\0\0\0"..., 784) = 784
lseek(3, 848, SEEK_SET)                 = 848
read(3, "\4\0\0\0\20\0\0\0\5\0\0\0GNU\0\2\0\0\300\4\0\0\0\3\0\0\0\0\0\0\0", 32) = 32
lseek(3, 880, SEEK_SET)                 = 880
read(3, "\4\0\0\0\24\0\0\0\3\0\0\0GNU\0\250\257l\201\313(\243{\363\245F\227\v\366B$"..., 68) = 68

mmap(NULL, 1844408, PROT_READ, MAP_PRIVATE|MAP_DENYWRITE, 3, 0) = 0x7f6735062000

mprotect(0x7f6735087000, 1654784, PROT_NONE) = 0
mmap(0x7f6735087000, 1351680, PROT_READ|PROT_EXEC, MAP_PRIVATE|MAP_FIXED|MAP_DENYWRITE, 3, 0x25000) = 0x7f6735087000
mmap(0x7f67351d1000, 299008, PROT_READ, MAP_PRIVATE|MAP_FIXED|MAP_DENYWRITE, 3, 0x16f000) = 0x7f67351d1000
mmap(0x7f673521b000, 24576, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_FIXED|MAP_DENYWRITE, 3, 0x1b8000) = 0x7f673521b000
mmap(0x7f6735221000, 13496, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_FIXED|MAP_ANONYMOUS, -1, 0) = 0x7f6735221000
close(3)                                = 0

arch_prctl(ARCH_SET_FS, 0x7f6735226500) = 0
mprotect(0x7f673521b000, 12288, PROT_READ) = 0
mprotect(0x55653cd13000, 4096, PROT_READ) = 0
mprotect(0x7f6735288000, 4096, PROT_READ) = 0
munmap(0x7f6735227000, 222529)          = 0
setdomainname(0x55653cd12004, 100)      = -1 EPERM (Operation not permitted)
exit_group(0)                           = ?
```
可以看到基本过程和ubuntu一样，都是读取文件（ld.so.cache，lib.so.6）并映射到内存,修改相应内存的属性。但是细节上稍微有些不同，比如一开始的arch_prctl（0x3001 /* ARCH_??? */, 0x7ffd252ee5b0），看起来是arch linux独有的。使用openat来打开文件，而不是open(有关open和openat的区别可参考 https://linux.die.net/man/2/openat， 简单来说openat更安全，避免race condition)。还有就是在libc的处理上，manjaro这里不停的lseek, read。

接下来看看静态编译的程序运行时所需的系统调用。

### 静态编译

```gcc -static setdomainname.c```


```bash=
execve("./a.out", ["./a.out"], 0x7ffe2f0d14e0 /* 58 vars */) = 0
arch_prctl(0x3001 /* ARCH_??? */, 0x7ffc45198680) = -1 EINVAL (Invalid argument)
brk(NULL)                               = 0x145a000
brk(0x145b1c0)                          = 0x145b1c0
arch_prctl(ARCH_SET_FS, 0x145a880)      = 0
uname({sysname="Linux", nodename="alex-pc", ...}) = 0

# readlink() places the contents of the symbolic link pathname in the
# buffer buf, which has size bufsiz.  readlink() does not append a null
# byte to buf.  It will (silently) truncate the contents (to a length
# of bufsiz characters), in case the buffer is too small to hold all of
# the contents.
readlink("/proc/self/exe", "/home/alex/syscall/a.out", 4096) = 24
brk(0x147c1c0)                          = 0x147c1c0
brk(0x147d000)                          = 0x147d000
setdomainname(0x47e004, 100)            = -1 EPERM (Operation not permitted)
exit_group(0)                           = ?
```
去掉动态链接后，系统调用变得简单很多。文件的读取和内存映射相关的系统调用都没有了。取而代之的是通过brk来分配内存。值得注意是readlink，他将读取符号链接（symbolic link）里面的内容并存入buf中。而[/proc/self/exe](http://man7.org/linux/man-pages/man5/proc.5.html)的作用是当execve产生的进程access这个link的时候将返回可执行程序的路径。合起来的效果就是进程找到相应的可执行文件的路径。接下来应该就是执行这个程序，但是这部分在系统调用的角度来看并不明显。

## 总结

在运行一个程序的时候，系统做了大量工作，主要是内存方面的分配和设置。但是具体的分配逻辑还是不太清晰，需要更进一步的学习和分析。
