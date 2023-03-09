---
Title: "Linux Kernel Implementation of a System Call"
Date: 2019-08-23T19:39:11+11:00
Summary: The previous article analyzed the system calls required for a simple C program to run. This article mainly analyzes what happens when the setdomainname system call is made.
draft: false
---

[The previous article analyzed a simple C program.](https://hackmd.io/wLxyRiQARP-ckNwXugW7bQ)（setdomainname.c）required a system call during runtime。This article mainly analyzes what happens when the setdomainname system call is made.

Firstly, the setdomainname system call is defined in the kernel as follows:
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

     // Acquire the write semaphore for the UTS namespace
    down_write(&uts_sem);

    // Set errno to indicate an error condition, then clear it if successful
    errno = -EFAULT;
    
    // Copy the domain name from userspace to kernel space
    if (!copy_from_user(tmp, name, len)) {
    
        // Get a pointer to the current UTS namespace
        struct new_utsname *u = utsname();
        memcpy(u->domainname, tmp, len);
        // Fill any remaining space in u->domainname with zeroes
        memset(u->domainname + len, 0, sizeof(u->domainname) - len);
        errno = 0;
    }
    
    // Release the write semaphore for the UTS namespace
    up_write(&uts_sem);
    return errno;
}

```
In summary, the function does the following:
1. Declare two local kernel variables.
2. Perform some permission and parameter checks.
3. Acquire a write semaphore for the UTS namespace.
4. Copy the domain name from userspace to kernel space, and store it in the current UTS namespace.
5. Release the write semaphore and return the result (either success or an error code).

The following mainly provides a more specific and further analysis of the last three steps. Since acquiring and releasing semaphore are basically inverse operations, they will be analyzed together.

## Acquiring and Releasing Read-Write Semaphores

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
    
    // How does the kernel acquire the lock?
    // raw_local_irq_save masks hardware interrupt
    // The main kernel implementation is in __lock_acquire, which is quite lengthy and involves lock validation. 
    rwsem_acquire(&sem->dep_map, 0, 0, _RET_IP_);

    // #define LOCK_CONTENDED(_lock, try, lock) lock(_lock)
    LOCK_CONTENDED(sem, __down_write_trylock, __down_write);
}

static inline void __down_write(struct rw_semaphore *sem)
{
    long tmp;

    // Add RWSEM_ACTIVE_WRITE_BIAS (0xffffffff00000001) to sem->count and return the incremented value. 
    // 并返回增加之后的值
    // it means that the write lock was already occupied, 
    // and rwsem_down_write_failed is called. 
    // For more details, see https://0xax.gitbooks.io/linux-insides/SyncPrim/linux-sync-5.html
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
    
    // Subtract RWSEM_ACTIVE_WRITE_BIAS from sem->count and return the result. 
    // If it is less than 0, it means that a writer is waiting for the read-write lock, 
    // so wake it up.
    if (unlikely(atomic_long_sub_return_release(RWSEM_ACTIVE_WRITE_BIAS,
                            &sem->count) < 0))
        // handle waking up a waiter on the semaphore
        rwsem_wake(sem);
}
```
During the entire fourth step, it remains in a write-lock state. The implementation and use of the lock are much more complicated than I expected. If interested, you can refer to [Synchronization primitives in the Linux kernel. Part 5](https://0xax.gitbooks.io/linux-insides/SyncPrim/linux-sync-5.html), which provides a detailed explanation. However, it's worth noting that the kernel version in this article is outdated, and operating on sem->count is still platform dependent. Newer versions of the kernel (after v5.1) have added general functions like atomic_long_sub_return_release, which reduce platform dependence and maintenance costs.


## copy_from_user

The kernel function copy_from_user is the core of the setdomainname system call and is a relatively complex part. It copies memory from the user space to the corresponding kernel space, thus implementing "set domain name". Various situations may arise during the process, such as what to do when there is a user space virtual memory page fault or if the memory addresses passed into copy_from_user are invalid. For those interested in the security issues related to copy_from_user, you can refer to [Two topics in user-space access](https://lwn.net/Articles/781283/)。Below, we will examine how the Linux kernel handles these problems in conjunction with the kernel source code.

```c=

static __always_inline unsigned long __must_check
copy_from_user(void *to, const void __user *from, unsigned long n)
{
    // check whether there is enough memory in kernel to copy
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
        // check whether the user space memnory is valid
        if (likely(access_ok(from, n))) {
            // check whether the to address belongs to kernel-memory
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
The next step is to continue analyzing the assembly code.

```c=

#define __get_user_asm_nozero(x, addr, err, itype, rtype, ltype, errret)	\
    // asm volatile to is protect code from being optimzed by compiler
    // GCC, the GNU C Compiler for Linux, uses AT&T/UNIX assembly syntax
    // "Op-code dst src" in Intel syntax changes to
    // "Op-code src dst" in AT&T syntax.
    // for more details, please see
    // https://www.ibiblio.org/gferg/ldp/GCC-Inline-Assembly-HOWTO.html
    asm volatile("\n"						\
             // assign the value of addr(src) to x(dest).
             "1:	mov"itype" %2,%"rtype"1\n"		\
             "2:\n"						\
             ".section .fixup,\"ax\"\n"				\
             "3:	mov %3,%0\n"				\
             "	jmp 2b\n"					\
             ".previous\n"					\
             // https://patchwork.kernel.org/patch/10579051/
             // looks like error handling
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

[UTS namespaces](https://lwn.net/Articles/179345/) is an important component of Linux virtualization technology. It enables processes to have their own independent hostname and domainname. This is also the technology that Docker's virtualized network relies on.

```c=
static inline struct new_utsname *utsname(void)
{   // Get the name of the uts_ns in the nsproxy of the current process.
    return &current->nsproxy->uts_ns->name;
}

struct nsproxy {
	atomic_t count;
	struct uts_namespace *uts_ns; // The "setdomainname" ultimately modifies this variable.
	struct ipc_namespace *ipc_ns;
	struct mnt_namespace *mnt_ns;
	struct pid_namespace *pid_ns_for_children;
	struct net 	     *net_ns;
	struct cgroup_namespace *cgroup_ns;
};
```

## Summary

Okay, the basic analysis of the system call setdomainname is almost complete here. This analysis journey turned out to be much longer and more important than I had imagined. Through the analysis of a system call, I learned about the specific implementation of Linux in reading and writing semaphores, how the kernel copies memory from user space to kernel space, and related virtualization techniques (even had a preliminary exposure to asm volatile, etc.). There were also many scenic spots along the way, but due to time constraints, I didn't delve into them carefully, such as the verification when acquiring locks, and other virtualization techniques (ipc, mnt, pid, etc.).

This was my first time analyzing the Linux kernel source code, and my overall impression was that it was rigorous and easy to read. I think there will be more kernel implementation analysis on other system calls in the future.