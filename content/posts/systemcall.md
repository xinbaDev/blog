---
title: "一个系统调用的linux内核实现"
date: 2019-08-23T19:39:11+11:00
summary: 前一篇文章研究分析了一个简单c程序运行时所需的系统调用。而这篇文章则主要分析，系统调用setdomainname时，到底发生了什么？
draft: false
---

[前一篇文章研究分析了一个简单c程序](https://hackmd.io/wLxyRiQARP-ckNwXugW7bQ)（setdomainname.c）运行时所需的系统调用。而这篇文章则主要分析，系统调用setdomainname时，到底发生了什么？

首先，setdomainname系统调用在内核中的定义如下：
```c=
SYSCALL_DEFINE2(setdomainname, char __user *, name, int, len)
{
    int errno;
    char tmp[__NEW_UTS_LEN];

    // #define CAP_SYS_ADMIN        21
    // /* Allow setting the domainname */
    if (!capable(CAP_SYS_ADMIN))
        return -EPERM;
    if (len < 0 || len > __NEW_UTS_LEN)
        return -EINVAL;

    // 获取读写信号量, 并对写上锁
    down_write(&uts_sem);
    // 先定义errno为出错的情况，然后如果成功，在errno=0
    // （为什么不直接在一开始声明的时候定义？）
    errno = -EFAULT;
    
    // 将用户空间的内存拷贝到内核空间的内存
    if (!copy_from_user(tmp, name, len)) {
    
        // uts namespace, 虚拟化技术
        struct new_utsname *u = utsname();
        // （为什么不直接拷贝到u->domainname，而是要通过局部变量tmp？）
        memcpy(u->domainname, tmp, len);
        // 多余的空间，填充 0 
        memset(u->domainname + len, 0, sizeof(u->domainname) - len);
        errno = 0;
    }
    
    // 释放读写信号量， 解锁
    up_write(&uts_sem);
    return errno;
}

```
可以看到，setdomainname主要做了5件事情。
1. 声明两个局部内核变量
2. 做一些权限和参数检查
3. 获取读写信号量，对写上锁
4. 将用户空间的变量拷贝到内核空间（tmp），然后将tmp的值复制到u->domainname中
5. 释放读写信号量，返回运行结果（成功或出错）

下面主要对后面3步进行更具体的进一步分析。因为对信号量的获取和释放基本是一对逆操作，所以将放在一起分析。

## 读写信号量的获取和释放

```c=
/*
 * lock for writing
 */
void __sched down_write(struct rw_semaphore *sem)
{   
    // Preemption must be disabled 
    // this macro just prints a stack trace if it was executed 
    // in atomic context
    might_sleep();
    
    // 内核是如何获得锁的？ 
    // 其中 raw_local_irq_save mask hardware interrupt
    // 主要内核实现在 __lock_acquire， 比较长， 涉及到lock验证，以后有空在分析
    rwsem_acquire(&sem->dep_map, 0, 0, _RET_IP_);

    // #define LOCK_CONTENDED(_lock, try, lock) lock(_lock)
    LOCK_CONTENDED(sem, __down_write_trylock, __down_write);
}

static inline void __down_write(struct rw_semaphore *sem)
{
    long tmp;

    // 将RWSEM_ACTIVE_WRITE_BIAS（0xffffffff00000001）加入sem->count， 
    // 并返回增加之后的值
    // 如果返回值不是0xffffffff00000001（一开始不是0），说明写锁之前已经被占用，
    // 并调用rwsem_down_write_failed， 具体可以参考
    // https://0xax.gitbooks.io/linux-insides/SyncPrim/linux-sync-5.html
    tmp = atomic_long_add_return_acquire(RWSEM_ACTIVE_WRITE_BIAS,
                         &sem->count);
    if (unlikely(tmp != RWSEM_ACTIVE_WRITE_BIAS))
        rwsem_down_write_failed(sem);
    rwsem_set_owner(sem); // write_once(sem->owner, current)
}

/*
 * unlock for writing
 */
void up_write(struct rw_semaphore *sem)
{
    // rwsem_acquire涉及到validator，这里不做进一步分析， 有兴趣可以参考：
    // https://www.kernel.org/doc/Documentation/locking/lockdep-design.txt
    rwsem_release(&sem->dep_map, 1, _RET_IP_);

    __up_write(sem);
}

static inline void __up_write(struct rw_semaphore *sem)
{
    DEBUG_RWSEMS_WARN_ON(sem->owner != current, sem);
    rwsem_clear_owner(sem);
    
    // 将sem->count减去RWSEM_ACTIVE_WRITE_BIAS，并返回
    // 如果小于0, 说明有writer在等读写锁，去唤醒之
    if (unlikely(atomic_long_sub_return_release(RWSEM_ACTIVE_WRITE_BIAS,
                            &sem->count) < 0))
        // handle waking up a waiter on the semaphore
        rwsem_wake(sem);
}
```
在整个第4步的过程中，都处于写锁状态。锁的实现和使用比我想象的要复杂的多，有兴趣可以看看[Synchronization primitives in the Linux kernel. Part 5](https://0xax.gitbooks.io/linux-insides/SyncPrim/linux-sync-5.html), 里面有详细的介绍。但是需要注意的是，该文章里面的内核是旧版的，在操作sem->count时还是platform dependent的。新版的内核（v5.1之后）中增加了atomic_long_sub_return_release等通用函数，减少了对平台的依赖，降低了维护成本。


## copy_from_user

copy_from_user的内核函数应该是setdomainname系统调用的核心，也是一个比较复杂的部分。将用户空间的内存拷贝到相应的内核空间，从而实现"set domain name"，中间可能出现种种状况。比如用户空间的虚拟内存缺页的时候怎么办？还有复制内存的时候，传入的用户空间的内存地址/内核空间地址不合法怎么办？关于copy_from_user的内核安全问题，有兴趣的可以看看[Two topics in user-space access](https://lwn.net/Articles/781283/)。下面结合内核源码来看看，linux内核是如何处理这些问题的。

```c=

static __always_inline unsigned long __must_check
copy_from_user(void *to, const void __user *from, unsigned long n)
{
    // 检查内核是否有足够空间去copy
    if (likely(check_copy_size(to, n, false)))
        n = _copy_from_user(to, from, n);
    return n;
}

#ifdef INLINE_COPY_FROM_USER
    static inline unsigned long
    _copy_from_user(void *to, const void __user *from, unsigned long n)
    {
        unsigned long res = n;
        // page fault might happen
        might_fault();
        // 检查用户空间的内存是否合法
        if (likely(access_ok(from, n))) {
            // 对to的地址是否属于kernel-memory检查，v4.7之后加入
            kasan_check_write(to, n);
            // raw_copy_from_user is platform dependent
            res = raw_copy_from_user(to, from, n);
        }
        if (unlikely(res))
            memset(to + (n - res), 0, res);
        return res;
    }
#else
    extern unsigned long
    _copy_from_user(void *, const void __user *, unsigned long);
#endif

// raw_copy_from_user is platform dependent
// for x86/64
static __always_inline __must_check unsigned long
raw_copy_from_user(void *dst, const void __user *src, unsigned long size)
{
    int ret = 0;

    if (!__builtin_constant_p(size))
        return copy_user_generic(dst, (__force void *)src, size);
    switch (size) {
    // 根据传入的大小，进行分别处理
    case 1:
        __uaccess_begin_nospec();
        __get_user_asm_nozero(*(u8 *)dst, (u8 __user *)src,
                  ret, "b", "b", "=q", 1);
        __uaccess_end();
        return ret;
        ...
    default:
        return copy_user_generic(dst, (__force void *)src, size);
    }
}

```
接下来在继续分析就是assembly code为主了。

```c=

#define __get_user_asm_nozero(x, addr, err, itype, rtype, ltype, errret)	\
    // asm volatile to is protect code from being optimzed by compiler
    // GCC, the GNU C Compiler for Linux, uses AT&T/UNIX assembly syntax
    // "Op-code dst src" in Intel syntax changes to
    // "Op-code src dst" in AT&T syntax.
    // 具体可参考 
    // https://www.ibiblio.org/gferg/ldp/GCC-Inline-Assembly-HOWTO.html
    asm volatile("\n"						\
             // 将addr(src)的值传给x(dest)
             "1:	mov"itype" %2,%"rtype"1\n"		\
             "2:\n"						\
             ".section .fixup,\"ax\"\n"				\
             // 将errret赋值给err
             "3:	mov %3,%0\n"				\
             "	jmp 2b\n"					\
             ".previous\n"					\
             // https://patchwork.kernel.org/patch/10579051/
             // 看起来和异常处理相关，难道这里会处理缺页异常？ 需要进一步确认
             _ASM_EXTABLE_UA(1b, 3b)				\
             // output list
             : "=r" (err), ltype(x)				\
             // input list
             : "m" (__m(addr)), "i" (errret), "0" (err))
             
static __always_inline __must_check unsigned long
copy_user_generic(void *to, const void *from, unsigned len)
{
    unsigned ret;

    /*
     * If CPU has ERMS feature, use copy_user_enhanced_fast_string.
     * Otherwise, if CPU has rep_good feature, use copy_user_generic_string.
     * Otherwise, use copy_user_generic_unrolled.
     */
    alternative_call_2(copy_user_generic_unrolled,
             copy_user_generic_string,
             X86_FEATURE_REP_GOOD,
             copy_user_enhanced_fast_string,
             X86_FEATURE_ERMS,
             ASM_OUTPUT2("=a" (ret), "=D" (to), "=S" (from),
                     "=d" (len)),
             "1" (to), "2" (from), "3" (len)
             : "memory", "rcx", "r8", "r9", "r10", "r11");
    return ret;
}
```

## utsname

[UTS namespaces](https://lwn.net/Articles/179345/)是重要的linux虚拟化技术组成之一。它使进程也可以拥有独立的hostname, domainname。这也是docker里面虚拟化网络所依赖的技术。

```c=
static inline struct new_utsname *utsname(void)
{   // 获得当前进程的nsproxy中的uts_ns的名字
    return &current->nsproxy->uts_ns->name;
}

struct nsproxy {
	atomic_t count;
	struct uts_namespace *uts_ns; // setdomainname最终修改的是这个变量
	struct ipc_namespace *ipc_ns;
	struct mnt_namespace *mnt_ns;
	struct pid_namespace *pid_ns_for_children;
	struct net 	     *net_ns;
	struct cgroup_namespace *cgroup_ns;
};
```

## Summary

好了，到这里基本完成了对setdomainname的系统调用的分析。这次分析之旅比我想象重要长，通过一个系统调用的分析，我学习了linux对读写信号量的具体实现，内核是如何拷贝用户空间的内存到内核空间，以及相关的虚拟化技术（甚至还初步接触了asm volatile等）。沿途还有许多风光，因为时间关系没有仔细深入去研究，比如对锁的获取时的验证，其他虚拟化技术（ipc, mnt, pid 等）。

第一次分析linux内核源码，给我的整体的印象是严谨，易读。我想之后应该会有更多关于其他系统调用的内核实现分析。