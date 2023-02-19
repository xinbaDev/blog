---
title: "记一次生产服务器debug(下)"
date: 2020-04-20T9:17:22+11:00
draft: true
summary: 在上一篇我们分析服务器的异常情况，并对导致异常的原因有了一个初步的判断。但是我们漏掉了一个关键的线索没有具体的分析，那就是cpu steal time。
---


在上一篇我们分析服务器的异常情况，并对导致异常的原因有了一个初步的判断。但是我们漏掉了一个关键的线索没有具体的分析，那就是cpu steal time。

## 什么是cpu steal time?


cpu steal time表现了cpu不够用的程度。cpu steal time的值越高，说明进程的cpu资源越不够。但是只是理解到这一层是不够的。cpu steal time是虚拟机中的一个指标，根据定义：

> Steal time is the percentage of time a virtual CPU waits for a real CPU while the hypervisor is servicing another virtual processor.

为了理解这个定义，我们首先要明白，在现代计算机中大量使用了虚拟化技术。尤其以云服务器器为例，一台实际的物理服务器上面常常会运行着多个虚拟的服务器（在aws中，这些服务器都被称作instance）。而这些virtual server（或者说instance）都会共用物理服务器的cpu。这样在看这个定义就好理解了。简单来说，本来应该给我们instace用的cpu资源被分配给其他instance用了，也就是所谓的cpu steal time。这种常常出现在服务提供方超售（over sale）的情况下出现。打个比方，本来一个服务器可以同时运行5个instance，但是我为了赚更多钱，我把这个服务器租给10个instace用，这样每个instance可以得到cpu资源自然就减少了。

![](https://i.imgur.com/FPchJRx.png)

                                steal cpu可以通过top指令查到。


那么难道AWS这么黑心，偷了本应属于我们cpu时间拿去卖，导致我们的node server不堪重负最后当掉吗？其实并没有，这还要从EC2 instance的一个特点说起。

## EC2中的t2 instace和cpu steal time

在EC2 instance中有一个相对特殊的类型，统称为T类。这种类型的instance有一个特点，他特别适合需要短期高负载的应用，在短期内这种instance可以提供超出其本身的cpu资源的能力。比如说你只付了small instance的钱，却可以短时间能得到medium instance才有的cpu资源。这种类型特别适合服务器，因为一般服务器的访问特点就是这样，短时间会有burst，但是大部分时间都是访问量是相对较低的，甚至大部分时间都是在baseline以下。有没有办法把那些低利用率时候的cpu资源攒起来，等高访问量时在释放出来呢? 

为了实现这个目的，aws提出了**cpu credit**的概念。比如当我们的服务器访问量较低，cpu使用率低的时候，系统会把没有充分利用的cpu存起来，以积分的形式加到cpu credit中，等访问量增大，cpu利用率增高，超出baseline的时候在释放出来，并扣掉相应的cpu credit。而当cpu credit扣完了，那cpu资源就只能用baseline所规定的大小了。

这也说明为什么在之前为了重现这个异常，我对服务器进行了压测，却无法重现异常的缘故了。因为当时cpu credit还没有到零，steal cpu的情况基本没有。所以服务器是按照超出baseline的cpu资源在运行。而服务器出事的时候cpu credit已经用完，当时cpu其实是以baseline的标准在运行。自然也就无法重现异常了。

分析到这里，上篇文章中的第2个问题已经有了答案。为什么重启node server没用，但是换一个服务器在开却可以。原因很显而易见了，重启的node server的cpu资源运行在cpu的baseline以下，cpu资源不足。而新的服务器会得到一定的初始cpu credit，可以在baseline以上运行，cpu够用。截图为证（左边是旧服务器，右边是新开服务器）：

![](https://i.imgur.com/TwNpizg.png)



## 重现异常及验证

当然以上都还只是根据异常所推理出的假设，实际验证还需要能够重现服务器之前的异常状况。为了重现这个异常，我对instance又进行了一次压力测试，不同的是这次测试时间比前一次长的多，直到让服务器的cpu credit减少到零。当cpu credit归零后，steal cpu爆增，服务器再次出现node server超长延时，甚至无法响应的情况，重现了上周服务器出现的异常。查看nginx的error log, 发现再次出现大量的110: connection time out, while reading response header from upstream, 再次确认这个异常复现成功。 

![](https://i.imgur.com/I3Bp0SD.png)


## 解决方法

找到出现问题的根源后，解决方法主要有以下几个：
1. 升级instance， 将t2.small升级到t2.medium。 t2.medium有两核cpu，而且比c2的服务器（cpu优化）的价格要便宜不少。
2. 开启t2 unlimited模式。在这种模式下，服务器可以超前预支一天的cpu credit，而当超过这个值后，服务器仍然可以全速运行，不过将按照$0.05/vcpu每小时收费。好处是不需要重启服务器，没有down time, 方便实现。
3. 通过kubernetes将node server部署到多台t2.small甚至t2.micro的机器上，使用负载均衡来减少单台服务器的loading。这个从长远的费用来说应该是最低的，而且可以提高可用性，避免单点故障。
4. 对node server的后端进行优化，根据初步对服务器代码调查，高度怀疑是graphql对cpu的消耗较大。对这块的优化可能可以带来较大的performance boost。但这一个解决方法也是最花时间的。
5. 对前端调用部分进行优化，利用懒加载的方式，减少对grahql api的调用。

个人目前倾向使用第二和第三条结合的方式，在完全迁移到kubernetes之前先打开unlimited的模式。不过之后有时间还是最好进行代码层面优化，也就是第4，第5条，分别对应了前后端的优化。


## Reference

1. https://mamchenkov.net/wordpress/2015/12/12/cpu-steal-time-now-on-amazon-ec2/
2. https://axibase.com/news/ec2-monitoring-the-case-of-stolen-cpu/
3. https://aws.amazon.com/cn/blogs/aws/new-t2-unlimited-going-beyond-the-burst-with-high-performance/