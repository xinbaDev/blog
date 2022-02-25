---
title: "系统调用open时到底发生了什么？（Linux内核学习笔记）"
date: 2020-12-21T16:50:11+11:00
summary: 在计算中系统中，最重要的有三类资源，分别是cpu, memory, disk，他们也是编程语言经常需要打交道的三类资源。比如cpu对应了语言的并发性(例如GO以高并发著称)，memory则涉及到语言的垃圾回收的机制，disk则是涉及到创建文件/删除文件等。应该说相比前两者，disk的部分是相对简单的。以python为例，一个简单的打开/创建文件，写入“hello world”，然后关闭文件的程序代码如下：
draft: false
---

在计算中系统中，最重要的有三类资源，分别是cpu, memory, disk，他们也是编程语言经常需要打交道的三类资源。比如cpu对应了语言的并发性(例如GO以高并发著称)，memory则涉及到语言的垃圾回收的机制，disk则是涉及到创建文件/删除文件等。应该说相比前两者，disk的部分是相对简单的。以python为例，一个简单的打开/创建文件，写入“hello world”，然后关闭文件的程序代码如下：

```python3=
## test.py

with open("test", "w") as fw:
    fw.write("hello world")
```

非常简单的一个程序，比起cpu，内存的各种操作，文件操作起来非常简单。我们来看看他的一些系统调用,```strace python3 test.py``` 走起：


运行python3程序时会先启动python的运行环境（虚拟机），读入脚本等操作，为了直观，这部分系统调用已经去掉。

```bash=
openat(AT_FDCWD, "test", O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0666) = 3
fstat(3, {st_mode=S_IFREG|0644, st_size=0, ...}) = 0
ioctl(3, TCGETS, 0x7ffcbd349ee0)        = -1 ENOTTY (Inappropriate ioctl for device)
lseek(3, 0, SEEK_CUR)                   = 0
ioctl(3, TCGETS, 0x7ffcbd349e70)        = -1 ENOTTY (Inappropriate ioctl for device)
stat("/home/alex", {st_mode=S_IFDIR|0700, st_size=4096, ...}) = 0
stat("/home/alex", {st_mode=S_IFDIR|0700, st_size=4096, ...}) = 0
stat("/home/alex", {st_mode=S_IFDIR|0700, st_size=4096, ...}) = 0
openat(AT_FDCWD, "/home/alex", O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_DIRECTORY) = 4
fstat(4, {st_mode=S_IFDIR|0700, st_size=4096, ...}) = 0
getdents64(4, /* 117 entries */, 32768) = 3832
getdents64(4, /* 0 entries */, 32768)   = 0
close(4)                                = 0
stat("/home/linuxbrew/.linuxbrew/Cellar/python/3.7.4_2/lib/python3.7", {st_mode=S_IFDIR|0755, st_size=12288, ...}) = 0
stat("/home/linuxbrew/.linuxbrew/Cellar/python/3.7.4_2/lib/python3.7/_bootlocale.py", {st_mode=S_IFREG|0444, st_size=1801, ...}) = 0
stat("/home/linuxbrew/.linuxbrew/Cellar/python/3.7.4_2/lib/python3.7/_bootlocale.py", {st_mode=S_IFREG|0444, st_size=1801, ...}) = 0
openat(AT_FDCWD, "/home/linuxbrew/.linuxbrew/Cellar/python/3.7.4_2/lib/python3.7/__pycache__/_bootlocale.cpython-37.pyc", O_RDONLY|O_CLOEXEC) = 4
fstat(4, {st_mode=S_IFREG|0644, st_size=1275, ...}) = 0
lseek(4, 0, SEEK_CUR)                   = 0
fstat(4, {st_mode=S_IFREG|0644, st_size=1275, ...}) = 0
read(4, "B\r\r\n\0\0\0\0\352\213#]\t\7\0\0\343\0\0\0\0\0\0\0\0\0\0\0\0\10\0\0"..., 1276) = 1275 
read(4, "", 1)                          = 0
close(4)                                = 0
lseek(3, 0, SEEK_CUR)                   = 0
write(3, "hello world", 11)             = 11
close(3)                                = 0
```

可以看为了创建一个test文件并写入"hello world"字串，python首先会调用openat的系统调用，并传入O_WRONLY|O_CREAT等flags去创建这个文件。接着fstate去获取这个文件的信息，通过ioctl去确认这个文件是普通文件而不是tty。然后用lseek去找到文件当前的位置。接下查了下文件所在的目录信息，还读取一个和编码相关_bootlocale程序。最后再通过调用write将"hello world"写入文件。比较奇怪的是lseek(3, 0, SEEK_CUR)调用了两次，分别在第4和第24行。ioctl也执行了两次，每次都传入一些奇怪的参数。

抛开奇怪的ioctl和lseek调用，我们这里主要研究这一行系统调用：

```bash=
openat(AT_FDCWD, "test", O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0666) = 3
# 剩下的3行之后在研究
# lseek(3, 0, SEEK_CUR)                   = 0
# write(3, "hello world", 11)             = 11
# close(3)                                = 0
```

这篇文章主要想讨论下文件系统是如何处理这个系统调用的。

首先来看看openat，功能和open一样，不过可以防止race condition，具体可以看[这里](http://man7.org/linux/man-pages/man2/openat.2.html)。从表面上看其功能就是返回一个文件的标识。根据我的理解，这个标识就是文件系统在disk上找到一块地方，然后对这个地方进行一个编号，然后将编号返回给程序。之后程序就可以通过这个编号，告诉文件系统对带有这个标号的文件进行操作。比较感兴趣的是这个fd和相关的数据在内存中的数据结构是怎么样的，以及文件系统这怎么在disk上找到这个地方？

还是看看linux kernel中的源码：

```c=
static long do_sys_openat2(int dfd, const char __user *filename,
			   struct open_how *how)
{
	struct open_flags op;
        
	int fd = build_open_flags(how, &op);
	struct filename *tmp;

	if (fd)
		return fd;

	tmp = getname(filename);
	if (IS_ERR(tmp))
		return PTR_ERR(tmp);
        //(1)fd是如何产生的？
	fd = get_unused_fd_flags(how->flags);
	if (fd >= 0) {
                //(2)如何打开这个文件？
		struct file *f = do_filp_open(dfd, tmp, &op);
		if (IS_ERR(f)) {
			put_unused_fd(fd);
			fd = PTR_ERR(f);
		} else {
			fsnotify_open(f);
			fd_install(fd, f);
		}
	}
	putname(tmp);
	return fd;
}

```
其中get_unused_fd_flags会调用__alloc_fd，阅读代码可以看到fd的由来，以及相关的一些数据结构。

```c=

int get_unused_fd_flags(unsigned flags)
{
	return __alloc_fd(current->files, 0, rlimit(RLIMIT_NOFILE), flags);
}

/*
 * allocate a file descriptor, mark it busy.
 */
 
//  struct files_struct {
//   /*
//    * read mostly part
//    */
// 	atomic_t count;
// 	bool resize_in_progress;
// 	wait_queue_head_t resize_wait;

// 	struct fdtable __rcu *fdt;  //__rcu是什么
// 	struct fdtable fdtab; // fdtable在此
//   /*
//    * written part on a separate cache line in SMP
//    */
// 	spinlock_t file_lock ____cacheline_aligned_in_smp;
// 	unsigned int next_fd;
// 	unsigned long close_on_exec_init[1];
// 	unsigned long open_fds_init[1];
// 	unsigned long full_fds_bits_init[1];
// 	struct file __rcu * fd_array[NR_OPEN_DEFAULT];
// };
int __alloc_fd(struct files_struct *files,
	       unsigned start, unsigned end, unsigned flags)
{
	unsigned int fd;
	int error;
    
        // struct fdtable {
        //     unsigned int max_fds;
        //     struct file __rcu **fd;      /* current fd array */
        //     unsigned long *close_on_exec;
        //     unsigned long *open_fds;
        //     unsigned long *full_fds_bits;
        //     struct rcu_head rcu;
        // };
	struct fdtable *fdt;

	spin_lock(&files->file_lock);
repeat:
        // 从files中拿fdtable
	fdt = files_fdtable(files);
        // 从0开始
	fd = start;
        // files里面保存了下一个fd
	if (fd < files->next_fd)
		fd = files->next_fd;

	if (fd < fdt->max_fds)
		fd = find_next_fd(fdt, fd);

	/*
	 * N.B. For clone tasks sharing a files structure, this test
	 * will limit the total number of files that can be opened.
	 */
	error = -EMFILE;
        // too many openfile
	if (fd >= end)
		goto out;

	error = expand_files(files, fd);
	if (error < 0)
		goto out;

	/*
	 * If we needed to expand the fs array we
	 * might have blocked - try again.
	 */
	if (error)
		goto repeat;

         // 更新files里面下一个fd
	if (start <= files->next_fd)
		files->next_fd = fd + 1;

        // static inline void __set_open_fd(unsigned int fd, struct fdtable *fdt)
        // {
        // 	__set_bit(fd, fdt->open_fds);
        // 	fd /= BITS_PER_LONG;
        // 	if (!~fdt->open_fds[fd])
        // 		__set_bit(fd, fdt->full_fds_bits);
        // }

	__set_open_fd(fd, fdt);
	if (flags & O_CLOEXEC)
    
        // static inline void __set_close_on_exec(unsigned int fd, struct fdtable *fdt)
        // {
        // 	__set_bit(fd, fdt->close_on_exec);
        // }
		__set_close_on_exec(fd, fdt);
	else
		__clear_close_on_exec(fd, fdt);
	error = fd;
#if 1
	/* Sanity check */
	if (rcu_access_pointer(fdt->fd[fd]) != NULL) {
		printk(KERN_WARNING "alloc_fd: slot %d not NULL!\n", fd);
		rcu_assign_pointer(fdt->fd[fd], NULL);
	}
#endif

out:
	spin_unlock(&files->file_lock);
	return error;
}


```

接下来第二个问题，系统如何打开这个文件的？

```c=
struct file *do_filp_open(int dfd, struct filename *pathname,
		const struct open_flags *op)
{

        // struct nameidata {
        //     struct path	path;
        //     struct qstr	last;
        //     struct path	root;
        //     struct inode	*inode; /* path.dentry.d_inode */
        //     unsigned int	flags;
        //     unsigned	seq, m_seq;
        //     int		last_type;
        //     unsigned	depth;
        //     int		total_link_count;
        //     struct saved {
        //         struct path link;
        //         struct delayed_call done;
        //         const char *name;
        //         unsigned seq;
        //     } *stack, internal[EMBEDDED_LEVELS];
        //     struct filename	*name;
        //     struct nameidata *saved;
        //     struct inode	*link_inode;
        //     unsigned	root_seq;
        //     int		dfd;
        // } __randomize_layout;
	struct nameidata nd;
	int flags = op->lookup_flags;
    
//     struct file {
//         union {
//             struct llist_node	fu_llist;
//             struct rcu_head 	fu_rcuhead;
//         } f_u;
//         struct path		f_path;
//         struct inode		*f_inode;	/* cached value */
//         const struct file_operations	*f_op;

//         /*
//          * Protects f_ep_links, f_flags.
//          * Must not be taken from IRQ context.
//          */
//         spinlock_t		f_lock;
//         enum rw_hint		f_write_hint;
//         atomic_long_t		f_count;
//         unsigned int 		f_flags;
//         fmode_t			f_mode;
//         struct mutex		f_pos_lock;
//         loff_t			f_pos;
//         struct fown_struct	f_owner;
//         const struct cred	*f_cred;
//         struct file_ra_state	f_ra;

//         u64			f_version;
//     #ifdef CONFIG_SECURITY
//         void			*f_security;
//     #endif
//         /* needed for tty driver, and maybe others */
//         void			*private_data;

//     #ifdef CONFIG_EPOLL
//         /* Used by fs/eventpoll.c to link all the hooks to this file */
//         struct list_head	f_ep_links;
//         struct list_head	f_tfile_llink;
//     #endif /* #ifdef CONFIG_EPOLL */
//         struct address_space	*f_mapping;
//         errseq_t		f_wb_err;
//     } __randomize_layout
//       __attribute__((aligned(4)));	/* lest something weird decides that 2 is OK */
        struct file *filp;

        // static void set_nameidata(struct nameidata *p, int dfd, struct filename *name)
        // {
        //     struct nameidata *old = current->nameidata;
        //     p->stack = p->internal;
        //     p->dfd = dfd;
        //     p->name = name;
        //     p->total_link_count = old ? old->total_link_count : 0;
        //     p->saved = old;
        //     current->nameidata = p;
        // }
        set_nameidata(&nd, dfd, pathname);
            //重点分析path_openat
        filp = path_openat(&nd, op, flags | LOOKUP_RCU);
        if (unlikely(filp == ERR_PTR(-ECHILD)))
            filp = path_openat(&nd, op, flags);
        if (unlikely(filp == ERR_PTR(-ESTALE)))
            filp = path_openat(&nd, op, flags | LOOKUP_REVAL);
        restore_nameidata();
        return filp;
    }

static struct file *path_openat(struct nameidata *nd,
			const struct open_flags *op, unsigned flags)
{
	struct file *file;
	int error;

        // f = kmem_cache_zalloc(filp_cachep, GFP_KERNEL);
	file = alloc_empty_file(op->open_flag, current_cred());
	if (IS_ERR(file))
		return file;

	if (unlikely(file->f_flags & __O_TMPFILE)) {
		error = do_tmpfile(nd, flags, op, file);
	} else if (unlikely(file->f_flags & O_PATH)) {
		error = do_o_path(nd, flags, file);
	} else {
                // 上面unlikely的就先不看，先抓主要部分
		const char *s = path_init(nd, flags);
                // 遍历 + 打开文件
		while (!(error = link_path_walk(s, nd)) &&
			(error = do_last(nd, file, op)) > 0) {
			nd->flags &= ~(LOOKUP_OPEN|LOOKUP_CREATE|LOOKUP_EXCL);
			s = trailing_symlink(nd);
		}
		terminate_walk(nd);
	}
	if (likely(!error)) {
		if (likely(file->f_mode & FMODE_OPENED))
			return file;
		WARN_ON(1);
		error = -EINVAL;
	}
	fput(file);
	if (error == -EOPENSTALE) {
		if (flags & LOOKUP_RCU)
			error = -ECHILD;
		else
			error = -ESTALE;
	}
	return ERR_PTR(error);
}
```

接下来我们主要分析do_last这个函数：

```c=

/*
 * Handle the last step of open()
 */
static int do_last(struct nameidata *nd,
		   struct file *file, const struct open_flags *op)
{
        // what is nd->path?
	struct dentry *dir = nd->path.dentry;
	kuid_t dir_uid = nd->inode->i_uid;
	umode_t dir_mode = nd->inode->i_mode;
	int open_flag = op->open_flag;
	bool will_truncate = (open_flag & O_TRUNC) != 0;
	bool got_write = false;
	int acc_mode = op->acc_mode;
	unsigned seq;
	struct inode *inode;
	struct path path;
	int error;

	nd->flags &= ~LOOKUP_PARENT;
	nd->flags |= op->intent;

	if (nd->last_type != LAST_NORM) {
		error = handle_dots(nd, nd->last_type);
		if (unlikely(error))
			return error;
		goto finish_open;
	}

	if (!(open_flag & O_CREAT)) {
		if (nd->last.name[nd->last.len])
			nd->flags |= LOOKUP_FOLLOW | LOOKUP_DIRECTORY;
		/* we _can_ be in RCU mode here */
		error = lookup_fast(nd, &path, &inode, &seq);
		if (likely(error > 0))
			goto finish_lookup;

		if (error < 0)
			return error;

		BUG_ON(nd->inode != dir->d_inode);
		BUG_ON(nd->flags & LOOKUP_RCU);
	} else {
		/* create side of things */
		/*
		 * This will *only* deal with leaving RCU mode - LOOKUP_JUMPED
		 * has been cleared when we got to the last component we are
		 * about to look up
		 */
		error = complete_walk(nd);
		if (error)
			return error;

		audit_inode(nd->name, dir, AUDIT_INODE_PARENT);
		/* trailing slashes? */
		if (unlikely(nd->last.name[nd->last.len]))
			return -EISDIR;
	}

        // 会进到这里来
	if (open_flag & (O_CREAT | O_TRUNC | O_WRONLY | O_RDWR)) {
		error = mnt_want_write(nd->path.mnt);
		if (!error)
			got_write = true;
		/*
		 * do _not_ fail yet - we might not need that or fail with
		 * a different error; let lookup_open() decide; we'll be
		 * dropping this one anyway.
		 */
	}
    
        // lock the inode 
	if (open_flag & O_CREAT)
        // static inline void inode_lock(struct inode *inode)
        // {
        //     down_write(&inode->i_rwsem);
        // }
		inode_lock(dir->d_inode);
	else
		inode_lock_shared(dir->d_inode);
         // 看起来非常重要的函数
	error = lookup_open(nd, &path, file, op, got_write);
	if (open_flag & O_CREAT)
		inode_unlock(dir->d_inode);
	else
		inode_unlock_shared(dir->d_inode);

	if (error)
		goto out;

	if (file->f_mode & FMODE_OPENED) {
		if ((file->f_mode & FMODE_CREATED) ||
		    !S_ISREG(file_inode(file)->i_mode))
			will_truncate = false;

		audit_inode(nd->name, file->f_path.dentry, 0);
		goto opened;
	}

	if (file->f_mode & FMODE_CREATED) {
		/* Don't check for write permission, don't truncate */
		open_flag &= ~O_TRUNC;
		will_truncate = false;
		acc_mode = 0;
		path_to_nameidata(&path, nd);
		goto finish_open_created;
	}

	/*
	 * If atomic_open() acquired write access it is dropped now due to
	 * possible mount and symlink following (this might be optimized away if
	 * necessary...)
	 */
	if (got_write) {
		mnt_drop_write(nd->path.mnt);
		got_write = false;
	}

	error = follow_managed(&path, nd);
	if (unlikely(error < 0))
		return error;

	/*
	 * create/update audit record if it already exists.
	 */
	audit_inode(nd->name, path.dentry, 0);

	if (unlikely((open_flag & (O_EXCL | O_CREAT)) == (O_EXCL | O_CREAT))) {
		path_to_nameidata(&path, nd);
		return -EEXIST;
	}

	seq = 0;	/* out of RCU mode, so the value doesn't matter */
	inode = d_backing_inode(path.dentry);
finish_lookup:
	error = step_into(nd, &path, 0, inode, seq);
	if (unlikely(error))
		return error;
finish_open:
	/* Why this, you ask?  _Now_ we might have grown LOOKUP_JUMPED... */
	error = complete_walk(nd);
	if (error)
		return error;
	audit_inode(nd->name, nd->path.dentry, 0);
	if (open_flag & O_CREAT) {
		error = -EISDIR;
		if (d_is_dir(nd->path.dentry))
			goto out;
		error = may_create_in_sticky(dir_mode, dir_uid,
					     d_backing_inode(nd->path.dentry));
		if (unlikely(error))
			goto out;
	}
	error = -ENOTDIR;
	if ((nd->flags & LOOKUP_DIRECTORY) && !d_can_lookup(nd->path.dentry))
		goto out;
	if (!d_is_reg(nd->path.dentry))
		will_truncate = false;

	if (will_truncate) {
		error = mnt_want_write(nd->path.mnt);
		if (error)
			goto out;
		got_write = true;
	}
finish_open_created:
	error = may_open(&nd->path, acc_mode, open_flag);
	if (error)
		goto out;
	BUG_ON(file->f_mode & FMODE_OPENED); /* once it's opened, it's opened */
	error = vfs_open(&nd->path, file);
	if (error)
		goto out;
opened:
	error = ima_file_check(file, op->acc_mode);
	if (!error && will_truncate)
		error = handle_truncate(file);
out:
	if (unlikely(error > 0)) {
		WARN_ON(1);
		error = -EINVAL;
	}
	if (got_write)
		mnt_drop_write(nd->path.mnt);
	return error;
}

int vfs_open(const struct path *path, struct file *file)
{
	file->f_path = *path;
	return do_dentry_open(file, d_backing_inode(path->dentry), NULL);
}

static int do_dentry_open(struct file *f,
			  struct inode *inode,
			  int (*open)(struct inode *, struct file *))
{
	static const struct file_operations empty_fops = {};
	int error;

	path_get(&f->f_path);
        // pass inode to file
	f->f_inode = inode;
	f->f_mapping = inode->i_mapping;

	/* Ensure that we skip any errors that predate opening of the file */
	f->f_wb_err = filemap_sample_wb_err(f->f_mapping);

	if (unlikely(f->f_flags & O_PATH)) {
		f->f_mode = FMODE_PATH | FMODE_OPENED;
		f->f_op = &empty_fops;
		return 0;
	}

	/* Any file opened for execve()/uselib() has to be a regular file. */
	if (unlikely(f->f_flags & FMODE_EXEC && !S_ISREG(inode->i_mode))) {
		error = -EACCES;
		goto cleanup_file;
	}

	if (f->f_mode & FMODE_WRITE && !special_file(inode->i_mode)) {
		error = get_write_access(inode);
		if (unlikely(error))
			goto cleanup_file;
		error = __mnt_want_write(f->f_path.mnt);
		if (unlikely(error)) {
			put_write_access(inode);
			goto cleanup_file;
		}
		f->f_mode |= FMODE_WRITER;
	}

	/* POSIX.1-2008/SUSv4 Section XSI 2.9.7 */
	if (S_ISREG(inode->i_mode) || S_ISDIR(inode->i_mode))
		f->f_mode |= FMODE_ATOMIC_POS;

	f->f_op = fops_get(inode->i_fop);
	if (WARN_ON(!f->f_op)) {
		error = -ENODEV;
		goto cleanup_all;
	}

	error = security_file_open(f);
	if (error)
		goto cleanup_all;

	error = break_lease(locks_inode(f), f->f_flags);
	if (error)
		goto cleanup_all;

	/* normally all 3 are set; ->open() can clear them if needed */
	f->f_mode |= FMODE_LSEEK | FMODE_PREAD | FMODE_PWRITE;
	if (!open)
		open = f->f_op->open;
	if (open) {
		error = open(inode, f);
		if (error)
			goto cleanup_all;
	}
	f->f_mode |= FMODE_OPENED;
	if ((f->f_mode & (FMODE_READ | FMODE_WRITE)) == FMODE_READ)
		i_readcount_inc(inode);
	if ((f->f_mode & FMODE_READ) &&
	     likely(f->f_op->read || f->f_op->read_iter))
		f->f_mode |= FMODE_CAN_READ;
	if ((f->f_mode & FMODE_WRITE) &&
	     likely(f->f_op->write || f->f_op->write_iter))
		f->f_mode |= FMODE_CAN_WRITE;

	f->f_write_hint = WRITE_LIFE_NOT_SET;
	f->f_flags &= ~(O_CREAT | O_EXCL | O_NOCTTY | O_TRUNC);

	file_ra_state_init(&f->f_ra, f->f_mapping->host->i_mapping);

	/* NB: we're sure to have correct a_ops only after f_op->open */
	if (f->f_flags & O_DIRECT) {
		if (!f->f_mapping->a_ops || !f->f_mapping->a_ops->direct_IO)
			return -EINVAL;
	}

	/*
	 * XXX: Huge page cache doesn't support writing yet. Drop all page
	 * cache for this file before processing writes.
	 */
	if ((f->f_mode & FMODE_WRITE) && filemap_nr_thps(inode->i_mapping))
		truncate_pagecache(inode, 0);

	return 0;

cleanup_all:
	if (WARN_ON_ONCE(error > 0))
		error = -EINVAL;
	fops_put(f->f_op);
	if (f->f_mode & FMODE_WRITER) {
		put_write_access(inode);
		__mnt_drop_write(f->f_path.mnt);
	}
cleanup_file:
	path_put(&f->f_path);
	f->f_path.mnt = NULL;
	f->f_path.dentry = NULL;
	f->f_inode = NULL;
	return error;
}

```

## Reference

1. https://stackoverflow.com/questions/1605195/inappropriate-ioctl-for-device
2. http://man7.org/linux/man-pages/man2/lseek.2.html
3. https://en.wikipedia.org/wiki/Ioctl
4. http://man7.org/linux/man-pages/man2/openat.2.html