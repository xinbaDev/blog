---
title: "Fallocate的那些事"
date: 2020-03-14T17:14:11+11:00
summary: fallocate是linux中的一个system call，他的主要作用是分配硬盘区块（block allocation）。我最初接触到这个命令是在本地测试一个程序的bug，这个bug需要在硬盘满了的时候才会触发。当时的硬盘空间还绰绰有余，需要想个办法把它快速填满。我知道linux中有个叫dd的命令可以往硬盘里写入指定大小的文件，我之前创建swap的时候就是用这个命令。但是这个命令用于创建大文件来说太久了。于是我想起之前在stackoverflow看到的另一个命令fallocate。据介绍，这个命令比dd快的多。一用之下，果然如此。
draft: false
---

fallocate是linux中的一个system call，他的主要作用是分配硬盘区块（block allocation）。
我最初接触到这个命令是在本地测试一个程序的bug，这个bug需要在硬盘满了的时候才会触发。当时的硬盘空间还绰绰有余，需要想个办法把它快速填满。我知道linux中有个叫dd的命令可以往硬盘里写入指定大小的文件，我之前创建swap的时候就是用这个命令。但是这个命令用于创建大文件来说太久了。于是我想起之前在stackoverflow看到的另一个命令fallocate。据介绍，这个命令比dd快的多。一用之下，果然如此。

```bash==
fallocate -l 5G test.img
```

5G的文件几乎瞬间生成，如果用dd去生成相同大小的文件不知道要多久。他的高效留给我很深的印象，同时让我十分好奇他的原理到底是什么？

于是先查了一下man。根据里面的介绍，fallocate除了可以给一个文件分配硬盘空间，他还支持取消分配（deallocate）。对于支持预分配的文件系统（filesystem），它可以快速分配区块（block），把他们标记成未初始化，而不需要对区块进行IO。这种方式比（比如dd）产生一个文件并向里面写0要快得多。

## 为什么需要Fallocate

其实与区块分配相关的system call一开始并不存在于linux系统中。对于应用程序，一般不需要涉及到分配区块的操作，这应该是内核需要干的活。但是后来还是引入linux系统。根据我看的资料，主要原因有两个。一个是从效率上出发，如果应用程序提前知道他需要写入的文件大小，那他可以提前通知内核在连续的地址上一次性分配完。这样可以减少多次调用内核去分配硬盘空间，好处大大的。首先减少内核调用（每次系统调用都涉及用户态和核心态的切换，这个过程是相对耗资源的），其次是加快对硬盘的写操作，因为分配的空间是连续的，不需要多次查找文件对应的区块（多次分配空间会导致一个文件散落在许多不连续的区块，增加查找时间）。

在以前，应用程序要提前分配的唯一方法就是先生成一个文件，然后往里面填充0。但是这种方法十分浪费，因为他需要先往硬盘里写入大量没用的数据（填充0）。于是就出现了fallocate。Falllocate把初始化的任务推后到真正需要写入的时候，从而避免一开始写入大量的无用数据。

在内部，fallocate这个系统调用（system call）并没有做很多事情，他只是调用文件系统里fallocate() inode operation。因此，每个文件系统都必须实现他自己的fallocate()。


## Fallocate的一些问题

在阅读fallocate的一些技术文献的，我碰到了一些有趣的[讨论](https://linux-ext4.vger.kernel.narkive.com/cP57aV67/rfc-patch-0-3-add-falloc-fl-no-hide-stale-flag-in-fallocate#post2)。

这个讨论来自linux mailing list里面的一封邮件。在这封邮件里提到Fallocate在一些文件系统上（比如ext4）似乎有些效能上的问题。有一些应用程序会对整个文件各个部分进行随机写入。当写入这些没有被初始化的部分时，文件系统需要对这些文件涉及到的区块做初始化，往往只是写入一小部分就要初始化一系列区块，让整个初始化变慢。邮件作者在淘宝工作中发现了这个问题，然后在一次workshop发现google也碰到过这个问题（具体可以看作者写的[workshop总结](https://www.aikaiyuan.com/1413.html)）。在邮件中他提出的解决方法是关闭fallocate的lazy initialization，将非初始化到初始化的cost去掉。这当然带来了不小的安全问题，因为这样旧的数据会被其他进程访问到。于是他又提出了通过加一个叫FALLOC_FL_NO_HIDE_STALE开关的方式来解决，默认关闭这个优化。之后他在自己电脑上做了测试，测试结果表示去掉初始化之后速度快了76%。


以下是他提交的patch中的3个commit:

[[RFC,1/3] vfs: add FALLOC_FL_NO_HIDE_STALE flag in fallocate](https://patchwork.ozlabs.org/patch/153251/)
[[RFC,2/3] vfs: add security check for _NO_HIDE_STALE flag](https://patchwork.ozlabs.org/patch/153250/)
[[RFC,3/3] ext4: add FALLOC_FL_NO_HIDE_STALE support](https://patchwork.ozlabs.org/patch/153249/)


在邮件讨论中，大部分的讨论者都不赞同这种解决方式，原因是这会带来很大的安全隐患。整个讨论基本上都是围绕效能和安全的取舍上。之后讨论逐渐转到为什么在初始化开启的情况下ext4的效能会比其他文件系统的受到更大的影响。作者又做了一系列测试，发现是ext4的journal机制所导致。Journal是文件系统保证数据完整性的机制。因为在一次写硬盘的操作时候往往会需要写好几个block，如果写其中一个block的时候不成功就会照成数据不完整。Journal的作用就是在写这些block之前先将要写的内容先保存起来，保存成功之后再写。其实journal的机制最早就是搞database那些人提出的。

在使用fallocate的时候，涉及到了文件的创建。这里面包括修改bitmap（分配i-node），添加文件名到目录，插入文件名到索引。这些操作都有可能中途失败。而为了保证数据完整性，Journal的把这些操作作为一个transcation，全部写入log。

扯远了，先回到作者的具体的测试代码和结果:

```bash=
time for((i=0;i<2000;i++)); do \
dd if=/dev/zero of=/mnt/sda1/testfile conv=notrunc bs=4k count=1 \
seek=`expr $i \* 16` oflag=sync,direct 2>/dev/null; \
done
```

```bash=
blktrace -d /dev/sda1
blkparse -i sda1.* -o blktrace.log
cat blktrace.log | grep 'D' | grep 'W' > result.log
```

[result (ext4)] （结果的含义可以参考这篇[文章](https://tunnelix.com/debugging-disk-issues-with-blktrace-blkparse-btrace-and-btt-in-linux-environment/)）
```
8,1 0 14 49.969995286 10 D WS 38011023 + 40 [kworker/0:1]
8,1 0 20 49.996170768 0 D WS 38011063 + 8 [swapper/0]
8,1 0 29 50.006811878 10011 D WS 278719 + 8 [dd]
8,1 0 31 50.013996421 10 D WS 38011071 + 24 [kworker/0:1]
8,1 0 37 50.029656811 0 D WS 38011095 + 8 [swapper/0]
8,1 1 70 50.039768259 10013 D WS 278847 + 8 [dd]
```


对比 [result (xfs)]
```
8,1 0 70 0.256951000 0 D WSM 40162600 + 3 [swapper/0]
8,1 1 50 0.271551873 12575 D WS 1311 + 8 [dd]
8,1 0 78 0.282466586 0 D WSM 40162603 + 3 [swapper/0]
8,1 1 55 0.296547264 12577 D WS 1439 + 8 [dd]
```

可以看到ex4的journal在每次写操作都会伴随写入两次，而xfs中journal只会伴随一次写, 而且写的block也比ext4要小的多（3 vs 40 + 8）。那为什么在ext4中会有两次写呢，是不是ext4比xfs多记录了什么东西？还有除了dd之外，kworker是和kernel相关的进程，swapper是linux中的idel进程（只有没有任何事情干了才会运行，但他又会对硬盘进行写操作？），似乎和journal本身关系不大？很遗憾，接下来邮件里的讨论没有继续这个话题。

关于这次讨论的结果是，这个patch最终因为安全隐患，没有被merge进kernel。而是加入的ext4中，通过ioctl可以去打开这个功能。其中是通过更改inode的方式去实现这个功能的，具体的代码[在此](https://patchwork.ozlabs.org/patch/167007/)。




## Reference

1. https://tunnelix.com/debugging-disk-issues-with-blktrace-blkparse-btrace-and-btt-in-linux-environment/
2. https://www.eecs.harvard.edu/~cs161/notes/journaling.pdf