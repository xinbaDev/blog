---
title: "通过架设wireguard我学到了什么"
date: 2019-11-24T12:39:11+11:00
summary: 最早接触wireguard应该是一年前左右的时候。当时觉得openvpn使用起来不是很稳定，想找一些更好的vpn开源程序。而且当时我也对vpn技术感兴趣，想找一个state of art来学习一下。于是wireguard就进入了我的眼帘。了解到wiredguard甚至进入了linux内核后，更加让我下定决心要花时间去学习架设这个vpn。虽然网上的教程很多，而且wireguard也是以容易架设著称，但是我的架设之路并不是一帆风顺。因为对wireguard不熟悉，也踩了不少坑，走了不少弯路。
draft: false
---

最早接触wireguard应该是一年前左右的时候。当时觉得openvpn使用起来不是很稳定，想找一些更好的vpn开源程序。而且当时我也对vpn技术感兴趣，想找一个state of art来学习一下。于是wireguard就进入了我的眼帘。了解到wiredguard甚至进入了linux内核后，更加让我下定决心要花时间去学习架设这个vpn。虽然网上的教程很多，而且wireguard也是以容易架设著称，但是我的架设之路并不是一帆风顺。因为对wireguard不熟悉，也踩了不少坑，走了不少弯路。

一开始我对wireguad基本一无所知，只是根据网上的教程，照猫画虎，安装wireguard，设置config。整个过程其实并不长，但是我对为什么这样设置，wireguard又是怎么根据这些设置来运作的这些并不了解。于是当我按照教程分别在服务器和本地架设好wireguard后去发现根本连不上的时候，我是束手无策的。

于是开始学习wireguard的工作原理。我先看了下wireguard的白皮书。白皮书里面首先提到了目前vpn的一些问题，比如代码过于复杂，容易产生安全漏洞等。然后介绍了wireguard如何解决这些问题，以及设计中的取舍等等。看完第一部分，wireguard给我的第一印象就是简单，安全和高效能。接下来的cryptokey routing是整个wireguard工作原理的核心，也是wireguard许多特性背后的原因（其中的Endpoints&Roaming部分让我想到之前在cloudflare上看到的一篇博文，里面也用到了public key来routing的技术）。接下来是第三部分Send/receive flow主要讲了wireguard的发送接收packet的过程，第四部分Basic usage讲了wireguard最简单的使用方法（这一部分非常简短，但是对理解wireguard的架设非常关键，之后会在详细介绍）。第5部分是protocol & cryptography, 也是非常重要的部分，主要涉及安全方面的考量，以及message的设计。第六部分是Timers & Stateless UX，第七部分linux kernel implementation，最后则是performace和conclusion。

这里主要提一下wireguard的发送流程和基本的使用方法。

1. 首先一个明文packet到达wireguard的interface, wg0 (至于怎么到达，之后会讲)
2. 获取packet的发送目标地址，192.168.87.21，这个地址匹配了其中一个peer TrMv...WXX0. 如果没有匹配到，则直接drop, 并返回一个ICMP“no route to host”, 同时返回一个 -ENOKEY到用户空间（这一步是在内核空间完成的）。
3. 使用对称加密key和一个与session相关nonce去加密这个明文packet, 使用的加密算法是 ChaCha20Poly1305
4. 添加一个header到这个加密后的packet。header的具体细节在5.4节中。
5. 这个packet被整个以UDP的方式发送到peer所对应的endpoint（internet地址）

而接收方其实是类似的流程，这里不再赘述。需要说明的是这里的明文packet就是ip packet, 根据wireguard的protocol，如果收到的packet最后是ip packet，最后会被drop掉。当时看到这里时我产生了一个问题，wireguard用的是udp进行传输，那他是怎么保证有序，流量控制和出错重传的呢？后来花时间看了下代码，确定wireguard里面没有tcp出错重传等等的机制，仔细想想其实也没有必要。wireguard应该是处于传输协议中第三层的协议，所以并不需要这些功能，wireguard也不是为了取代tcp/udp这些协议。

在第四部分Basic usage中，我们其实可以看到wireguard在linux下简单的架设过程。这里以client为重点，学习分析一下wireguard在client端是怎么运作的，需要做哪些准备，packet又是怎么样才能到wireguard的interface的。

```
$ ip link add dev wg0 type wireguard
$ ip address add dev wg0 10.192.122.3/24
$ ip route add 10.0.0.0/8 dev wg0

$ ip address show

1: lo:  mtu 65536inet 127.0.0.1/8 scope host lo
2: eth0:  mtu 1500inet 192.95.5.69/24 scope global eth0
3: wg0:  mtu 1420inet 10.192.122.3/24 scope global wg0
```

可以看到在运行完3个ip开头的命令之后，一个叫wg0的interface就出现了。这三个命令分别设置了wg0 network interface的类型，ip, 和相应的route。这些命令的具体功能都可以在linux下通过man ip link/address/route查到。简单来讲，有了这个虚拟的device interface, 以后destination在10.0.0.0/8范围的packet都会到这个interface中。而wireguard则是监听这个device，当有packet来到的时候就会进行，检查，加密，加header，发送等一系列操作。为了架设方便，wireguard提供了一个wg-quick的shell脚本，网上很多教程都利用到了这个脚本。其实wg-quick最主要的部分就是设置wg0这个interface。，其中又主要用到了ip这个命令，通过man wg-quick也可以看到这个命令的具体介绍。以下是其中一些重要的函数。

```bash=
cmd_up() {
	local i
	[[ -z $(ip link show dev "$INTERFACE" 2>/dev/null) ]] || die "\`$INTERFACE' already exists"
	trap 'del_if; exit' INT TERM EXIT
	execute_hooks "${PRE_UP[@]}"
	add_if
	set_config
	for i in "${ADDRESSES[@]}"; do
		add_addr "$i"
	done
	set_mtu_up
	set_dns
	for i in $(while read -r _ i; do for i in $i; do [[ $i =~ ^[0-9a-z:.]+/[0-9]+$ ]] && echo "$i"; done; done < <(wg show "$INTERFACE" allowed-ips) | sort -nr -k 2 -t /); do
		add_route "$i"
	done
	execute_hooks "${POST_UP[@]}"
	trap - INT TERM EXIT
}

add_route() {
	local proto=-4
	[[ $1 == *:* ]] && proto=-6
	[[ $TABLE != off ]] || return 0

	if [[ -n $TABLE && $TABLE != auto ]]; then
		cmd ip $proto route add "$1" dev "$INTERFACE" table "$TABLE"
	elif [[ $1 == */0 ]]; then
		add_default "$1"
	else
		[[ -n $(ip $proto route show dev "$INTERFACE" match "$1" 2>/dev/null) ]] || cmd ip $proto route add "$1" dev "$INTERFACE"
	fi
}
```
其中在add_route中，脚本会根据wg0.conf中的设置作出相应的配置。比如在client中peer下面的allowedIP中，如果是0.0.0.0/0, add_route会调用add_default, 而其中又会添加0.0.0.0：/的route, 设置防火墙， iptable等等。所以这个也是client通过wireguard代理访问internet的关键，否则如果按照论文那样设置10.0.0.0/8，就起不到代理的作用。结果是虽然能ping到wireguard server, 但是访问Internet还是不会经过wreguard的服务器。

看完白皮书，和网上的一些教程后，我又看了wireguard的源码。根据wireguard作者的说法，wireguard只有几千行代码，花一个下午就可以看完。在加上linux之父Linus对wireguard的源代码也赞赏有加。于是我很快找来代码看了看。我先看的是wireguard-go, 之后有看了wireguard-linux。相比之下，go语言写的wireguard好懂很多。整个程序都跑在user space，复杂的部分很多都封装起来了，看起来相对轻松。c语言写的wireguard-linux就相对不那么直观了。因为涉及的内核操作，如果对linux内核不熟悉，看起来还是比较费劲，换句话说就是学习曲线比较陡。当然从运行效率来说, 在内核空间运行的wireguard-linux比在用户空间的wireguard-go要高多了。白皮书中performace环节也是以内核态运行的wireguard作为标准进行比较。

目前我对wireguard的源代码看的还并不多，主要看了下wireguard-go的入口main函数，以及其中一些比较重要的组成部分，比如device, tun等。
