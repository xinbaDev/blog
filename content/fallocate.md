---
Title: "All About Fallocate"
Date: 2020-03-14T17:14:11+11:00
Summary: Fallocate is a system call in Linux that is mainly used for block allocation on the hard disk. I first came across this command while testing a bug in a program locally. The bug only triggered when the hard disk was full, but there was still plenty of space left on it. I needed a way to quickly fill up the remaining space. I knew there was a command in Linux called 'dd' that could write a file of a specified size to the hard disk. I had used this command before when creating a swap. However, this command was too slow when it came to creating large files. Then I remembered another command I had seen on StackOverflow called 'fallocate'. According to its introduction, this command is much faster than 'dd'. As soon as I tried it, I found it to be true.
draft: false
---

Fallocate is a system call in Linux that is mainly used for block allocation on the hard disk. I first came across this command while testing a bug in a program locally. The bug only triggered when the hard disk was full, but there was still plenty of space left on it. I needed a way to quickly fill up the remaining space. I knew there was a command in Linux called 'dd' that could write a file of a specified size to the hard disk. I had used this command before when creating a swap. However, this command was too slow when it came to creating large files. Then I remembered another command I had seen on StackOverflow called 'fallocate'. According to its introduction, this command is much faster than 'dd'. As soon as I tried it, I found it to be true.

```bash==
fallocate -l 5G test.img
```

The file generated by 5G is almost instant, and it's unknown how long it would take to generate a file of the same size using dd. Its efficiency left a deep impression on me, and I was very curious about its principles.

So I first looked at the man page. According to the introduction in it, fallocate not only can allocate hard disk space for a file, but also supports deallocation. For file systems that support pre-allocation, it can quickly allocate blocks and mark them as uninitialized without performing any I/O on the blocks. This method is much faster than creating a file and writing 0 to it using dd.

## Why do we need fallocate

Actually, the system calls related to block allocation did not initially exist in the Linux system. Generally, applications do not need to involve block allocation operations, as this should be done by the kernel. However, it was later introduced into the Linux system. According to the information I have read, there are two main reasons for this. One is efficiency-based: if the application program knows in advance the size of the file it needs to write, it can notify the kernel in advance to allocate it all at once on contiguous addresses. This can reduce the number of times the kernel is called to allocate hard disk space, which has a significant advantage. Firstly, it reduces kernel calls (each system call involves switching between user mode and kernel mode, which is relatively resource-consuming), and secondly, it speeds up the writing operation to the hard disk, as the allocated space is contiguous, and there is no need to look for the corresponding blocks of the file multiple times (multiple space allocations will cause a file to be scattered in many discontinuous blocks, increasing the lookup time).

Previously, the only way for an application program to allocate space in advance was to first generate a file and then fill it with 0s. However, this method is very wasteful because it needs to write a lot of useless data (filling with 0s) to the hard disk first. So fallocate was developed. Fallocate postpones the initialization task until it is really needed to be written, thereby avoiding the initial writing of a large amount of useless data.

Internally, the fallocate system call does not do much. It simply calls the fallocate() inode operation in the file system. Therefore, each file system must implement its own fallocate().


## Some issues with fallocate

When reading some technical literature about fallocate, I came across some interesting [discussions](https://linux-ext4.vger.kernel.narkive.com/cP57aV67/rfc-patch-0-3-add-falloc-fl-no-hide-stale-flag-in-fallocate#post2).

This discussion comes from an email in the Linux mailing list. In this email, it is mentioned that fallocate seems to have some performance issues on some file systems (such as ext4). Some applications will randomly write to various parts of the entire file. When writing to these uninitialized parts, the file system needs to initialize the blocks involved in these files. Often, only a small part is written, but a series of blocks need to be initialized, making the entire initialization slower. The author of the email discovered this problem while working at his companyh and then at a workshop, found that Google had also encountered this problem. see the author's workshop summary for [details](https://www.aikaiyuan.com/1413.html). In the email, he proposed a solution to turn off fallocate's lazy initialization and remove the  initialized cost. Of course, this brought some security issues because old data would be accessed by other processes. So he proposed a way to solve this problem by adding a switch called FALLOC_FL_NO_HIDE_STALE, which is closed by default. He then tested this on his computer and found that removing the initialization resulted in a 76% speed increase.


The following are 3 commits in the patch he submitted:

- [[RFC,1/3] vfs: add FALLOC_FL_NO_HIDE_STALE flag in fallocate](https://patchwork.ozlabs.org/patch/153251/)

- [[RFC,2/3] vfs: add security check for _NO_HIDE_STALE flag](https://patchwork.ozlabs.org/patch/153250/)

- [[RFC,3/3] ext4: add FALLOC_FL_NO_HIDE_STALE support](https://patchwork.ozlabs.org/patch/153249/)


In the email discussion, most of the participants disagreed with this solution because it would bring significant security risks. The entire discussion was basically focused on the trade-off between efficiency and security. Later, the discussion gradually turned to why the performance of ext4 was more affected than other file systems when initialized. The author conducted a series of tests and found that it was due to the journal mechanism of ext4. The journal is a mechanism for the file system to ensure data integrity. Because when writing to the hard disk, several blocks often need to be written in one operation. If one of the blocks fails to be written successfully, it will cause data incompleteness. The role of the journal is to first save the content to be written before writing these blocks, and then write it after the save is successful. In fact, the journal mechanism was originally proposed by those who worked on databases.

When using fallocate, file creation is involved. This includes modifying the bitmap (allocating i-nodes), adding the file name to the directory, and inserting the file name into the index. These operations may fail halfway. In order to ensure data integrity, the journal treats these operations as a transaction and writes them all to the log.

Getting back to the author's specific test code and results:

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

[result (ext4)] （The meaning of the result can be referred to in this [article](https://tunnelix.com/debugging-disk-issues-with-blktrace-blkparse-btrace-and-btt-in-linux-environment/)).
```
8,1 0 14 49.969995286 10 D WS 38011023 + 40 [kworker/0:1]
8,1 0 20 49.996170768 0 D WS 38011063 + 8 [swapper/0]
8,1 0 29 50.006811878 10011 D WS 278719 + 8 [dd]
8,1 0 31 50.013996421 10 D WS 38011071 + 24 [kworker/0:1]
8,1 0 37 50.029656811 0 D WS 38011095 + 8 [swapper/0]
8,1 1 70 50.039768259 10013 D WS 278847 + 8 [dd]
```


compare with [result (xfs)]
```
8,1 0 70 0.256951000 0 D WSM 40162600 + 3 [swapper/0]
8,1 1 50 0.271551873 12575 D WS 1311 + 8 [dd]
8,1 0 78 0.282466586 0 D WSM 40162603 + 3 [swapper/0]
8,1 1 55 0.296547264 12577 D WS 1439 + 8 [dd]
```

We can see that in ex4, the journal is written twice with every write operation, while in xfs, the journal is only written once. Additionally, the block written in xfs is much smaller than in ext4 (3 vs 40 + 8). So why is there a double write in ext4? Did ext4 record something extra compared to xfs? Also, besides dd, kworker is a process related to the kernel, and swapper is an idle process in Linux (which only runs when there is nothing to do, but does it also perform write operations on the hard drive?). It seems that these processes are not directly related to the journal. Unfortunately, the email discussion did not continue on this topic.

The result of this discussion was that the patch was not merged into the kernel due to security concerns, but instead was added to ext4. This functionality can be enabled through ioctl. The patch achieved this by changing the inode, and the specific code can be found [here](https://patchwork.ozlabs.org/patch/167007/).


## Reference

1. https://tunnelix.com/debugging-disk-issues-with-blktrace-blkparse-btrace-and-btt-in-linux-environment/
2. https://www.eecs.harvard.edu/~cs161/notes/journaling.pdf