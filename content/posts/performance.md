---
title: "关于服务优化的调研和思考"
date: 2020-04-11T11:14:22+11:00
draft: false
summary: 最近某台服务器的cpu使用率一直居高不下，直接导致用户等待时间增加，用户体验明显变差。甚至还出现了服务器几乎当机的情况。所以想研究一下有没有办法通过代码层面优化的方式减少cpu的使用率。
---

最近某台服务器的cpu使用率一直居高不下，直接导致用户等待时间增加，用户体验明显变差。甚至还出现了服务器几乎当机的情况。所以想研究一下有没有办法通过代码层面优化的方式减少cpu的使用率。

## 1. 线索搜集

### 1.1. 应用的一些信息

1. 这台服务器主要跑的应用是node server。node的版本是v10.16.0。
2. node server所使用到的主要框架有（只列举我认为重要的一部分）：
    - strapi: 3.0.0-alpha.26.1
    - knex: latest
    - pg: 7.10.0
    - graphql: 14.1.0
    - pluralize: 7.0.0
    - apollo-server-koa: 2.0.7
    - dataloader: 1.4.0
3. 应用代码基本上都是strapi的框架自动生成。手写的业务逻辑代码不多。



### 1.2. 一些简单的profile

1. 使用node自带的prof，```node --prof server.js```, 测试时长为1分钟，测试结果：
```
  [Summary]:
   ticks  total  nonlib   name
   3319   33.1%   34.0%  JavaScript
   6336   63.2%   64.8%  C++
    161    1.6%    1.6%  GC
    254    2.5%          Shared libraries
    
  [C++]: （只显示前三）
   ticks  total  nonlib   name
   2370   23.6%   24.3%  epoll_pwait
    816    8.1%    8.4%  node::contextify::ContextifyScript::New(v8::FunctionCallbackInfo<v8::Value> const&)
    304    3.0%    3.1%  node::fs::Read(v8::FunctionCallbackInfo<v8::Value> const&)

  [JavaScript]: （只显示前三）去
   ticks  total  nonlib   name
    329    3.3%    3.4%  Builtin: InterpreterEntryTrampoline
    191    1.9%    2.0%  Builtin: CallFunction_ReceiverIsAny
    133    1.3%    1.4%  Builtin: KeyedLoadIC_Megamorphic


  [C++ entry points]: （只显示10%以上）
   ticks    cpp   total   name
   1573   42.5%   15.7%  v8::internal::Builtin_HandleApiCall(int, v8::internal::Object**, v8::internal::Isolate*)
    395   10.7%    3.9%  v8::internal::Runtime_CompileLazy(int, v8::internal::Object**, v8::internal::Isolate*)
    
```
2. 使用[clinic](https://github.com/nearform/node-clinic)对应用进行profile（包括strapi应用，依赖， nodejs, 以及v8）

![](https://i.imgur.com/5zbT0Jg.png)


## 2. 初步的一些判断

### 2.1. profile之前
1. 首先这个应用基本是自动生成的，手写的业务代码很少，应用代码导致的cpu使用率高的可能性很小。
2. 注意到这个程序用到graphql, knex等框架，涉及到parsing, analysis, compile等消耗cpu的操作。根据以往的经验，这块导致cpu使用率升高的可能性较大。

### 2.2. profile之后

1. 发现epoll_pwait这个调用占了较大的cpu使用，查了下发现在node v10的版本存在epoll_pwait相关的bug会导致[cpu使用率飙高](https://github.com/libuv/libuv/pull/2166)的情况。虽然和我们的情况不同，但是可以调查一下。
2. 通过clinic的profile报告，可以看到依赖用掉了绝大部分了cpu，其中knex和pg这两个依赖用去较多cpu（但总的来讲也并不多）。knex是用来生成sql query，消耗较多cpu是意料之中的，比较意外的是graphql相关的依赖在消耗cpu方面没有特别突出。
3. 整个profile下来，没有看到明显的突出占用cpu的部分，基本上是均匀分布。

总的来说，我初步的判断就是这个应用本身是cpu intensive, 并没有特别明显的瓶颈。

## 3. 一些优化思路

虽然没有明显瓶颈，但是代码层面的优化也还是存在空间的。

1. 首先是graphql server方面的优化。
graphql server在处理请求的时候需要先parsing，validate,然后在设计出execution plan。在这个过程中涉及到了大量计算，我相信是存在优化空间的。

2. 还有就是前端对graphql的调用，除了通过懒加载的方式减少不必要的调用外，是不是还可以通过优化query的方式来减少graphql的计算量呢？

3. 再有就是knex方面的优化。knex也涉及不少计算，比如sql query的compile部分。通过profile也可以看到这部分是相对吃cpu的，在cpu使用率占比中名列前茅。

4. 对应用进行更细致的profile, 精确到每一个graphql的api调用，更加具体的研究调用的流程。profile是优化的基础，非常重要。

暂时思路就是这些，因为对graphql, knex等技术并不熟悉，等调研学习之后有了更深了解在补上。

## 4. 优化调研

目前看到的一些相关的优化经验和工具(持续增加中)：

1. https://medium.com/@wtr/graphql-performance-explained-cb4b43412fb4
2. https://github.com/zalando-incubator/graphql-jit#readme
3. 。。。

## reference
1. https://nodejs.org/en/docs/guides/simple-profiling/
2. https://medium.com/@wtr/graphql-performance-explained-cb4b43412fb4
3. https://github.com/libuv/libuv/pull/2166