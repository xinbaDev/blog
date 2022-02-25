---
title: "如何确认Email是否真实存在"
date: 2019-06-30T20:17:00+11:00
summary: 最近公司在做promotion,导致有许多刷注册的帐号。这些帐号都留下虚假的邮箱，导致发送确认邮箱的邮件经常无法送达，导致bounce rate提高了不少，甚至一度超过aws ses的警戒线。根据aws的规定，超过一定界限，会停止发送邮件的服务。为了防止被禁用，如何识别这些虚假邮箱，降低bounce rate就成了我需要解决的问题。
draft: false
---

最近公司在做promotion,导致有许多刷注册的帐号。这些帐号都留下虚假的邮箱，导致发送确认邮箱的邮件经常无法送达，导致bounce rate提高了不少，甚至一度超过aws ses的警戒线。根据aws的规定，超过一定界限，会停止发送邮件的服务。为了防止被禁用，如何识别这些虚假邮箱，降低bounce rate就成了我需要解决的问题。经过一些调研和实验，我对email验证这块有了一些心得，并记录如下。

## 原理
验证Email是否存在（或者说是否会[hard bounce](https://whatis.techtarget.com/definition/hard-bounce)）的原理并不复杂。
主要可以分为两步。

（1） 获取和检验邮箱域名

        邮箱域名可以通过nslookup -query=MX domain name获得
        比如nslookup -query=MX 61financial.com.au
        其中的email exchanger就是邮箱域名。可以看到61financial用的是outlook的邮件服务器

（2） 如果邮箱域名存在，根据邮箱域名连接到对应服务器，验证邮箱。

        连接上邮件服务器之后，有两种验证邮箱存在与否的方式。第一种是直接发送verify指令来验证。有些邮箱服务支持verify指令， 
        比如163, 126 qq等国内邮箱。但有些邮箱服务，比如gmail, hotmail, outlook是不支持的。

>>> [Mailtester](http://mailtester.com/testmail.php)就使用了第一种的验证方式，所以gmail是没办法验证的。

        
        这时就需要使用第二种方式，直接给目标邮件发送一封邮件（其实不需要真正发送，只要作出想要发送的动作就可以了）。
        根据RFC5321, 在和邮件服务器沟通的过程中时候， 当发送邮件的一方发出
        REPT TO: <emaill address>的指令给邮箱接受方的时候，邮件接收方需要返回是否成功。这一步也是检验邮箱是否被接受的关键。
        以gmail为例，当邮箱存在的时候，会返回250 OK， 而如果不存在，则会返回550（也就是hard bounce）。 
        
        需要注意的是，并不是所有返回250都代表邮箱存在，outlook就是反例。outlook邮箱在处理邮件接收的时候和其他主流
        mail server不同。不管邮箱是否存在，他都会先将邮件先接收下来(accept all)，之后如果无法递送，
        才会发送一封邮件返回发送方说明邮件无法送出。这也是我之前说的，为什么叫bounce eliminator更准确，
        因为这个方法只能判断邮件是否被接受(2019/06/20 Update: 现在如果邮箱不存在，outlook也会返回500+的error了)。

        PS: 能否做到100%的邮箱验证？ 理论上来说是可以的，比如对于outlook就可以通过监控之后出错邮件来判断邮箱是否存在。
        但是根本没有必要。因为减少hard bounce才是我们一开始的目的。 市面上几乎所有的关于email verification的服务，不管
        收费与否也都是基于此原理。


## 调用

使用rest api来调用。

Request: 
https://endpont/?email=xxxx@xx.com

Response:
```
{
    "allow_send": False,
    "status_code": 1,
    "reason": "invalid email"
}
```
想要了解更多关于这个api是如何工作，建议读我的源码，里面有充足的注解，包括各种设计的考量，相信你看完之后会对这个api有更深的了解。

## AWS serverless

为什么使用serverless的形式部署。 主要是为了[省钱](https://aws.amazon.com/cn/lambda/pricing/)，方便。不需要操心server的部署。而且作为一个比较基础的功能，以后有其他服务需要调用也会很方便。

关于部署， 在email_verify的目录下，运行bash makezip.sh(该脚本会在zip目录下生成lambda_function.zip), 然后将生成的zip文件上传到aws lambda console上。具体步骤可以参考 https://docs.aws.amazon.com/lambda/latest/dg/getting-started.html

部署好lambda function后，然后添加trigger。aws支持多种triggers（如load balancer, s3等等），本micro service用的是 Api gateway作为trigger。 以上都可以通过aws提供图形界面完成，相信并不难。而且我碰到的一些坑都在lambda_function.py里面有注释。

一些关于api gateway的文档： 

https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-call-api.html
https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-test-method.html