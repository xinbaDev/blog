---
Date: 2024-08-07 22:30:11+09:00
Summary: I've been using LastPass as my password manager for many years. It has become
  an indispensable tool for all my internet browsing activities. However, a few years
  ago an incident occurred - LastPass was hacked. This security breach prompted me
  to consider switching to a different password manager, ideally one that I could
  manage myself for personalized security. Recently, I found the time to execute my
  plan to transition from LastPass to Bitwarden, an open-source alternative. In this
  post, I will discuss the measures I took to ensure its secure functionality, providing
  assurance that my passwords are safe and enabling me to have peace of mind.
Title: How can I protect my password effectively?
draft: true
---

I've been using LastPass as my password manager for several years and it had become indispensable for my internet browsing. However, a few years ago an unfortunate incident unfolded; LastPass was hacked. Since that incident, thoughts of changing my password manager have continuously lingered in my mind, ideally to a self-managed password manager that only serves my needs. Recently, I found the time to execute my plan to switch from LastPass to Bitwarden, an open-source alternative. In this post, I will discuss how I successfully secured Bitwarden, providing me the peace of mind to sleep well knowing that my passwords are safe and sound.


## Methods Employed

As the sole user of this password manager, I am able to implement security measures not available in public password managers. These measures primarily aim to reduce the attack surface or minimize the time during which an attack could occur. The following describes a few methods I have employed in my personalized password manager.


### 1. Incorporating a Secret Key into a Custom Header

The first step I take is to incorporate a secret key into every request header. The server will scrutinize this request header to decide whether the request originates from a valid source. If the header is absent from the request, or the secret incorporated in the custom header is incorrect, the request won't even reach the API backend. Instead, the server will simply abort the request. This method is extremely popular and easy to implement, which is why it was the first solution that came to mind and which I chose to implement.


### 2. Implementing a Prefix to Each API Endpoint

The second enhancement I implemented was the addition of a UUID (Universally Unique Identifier) to every API endpoint. For instance, "/user" would transform into a URL similar to "62cff9cf-9166-495a-a92a-9101d9e1aa78/user". This straightforward alteration proves effective in making directory traversal tools like Gobuster ineffectual. A similar approach is implemented by Telegram for its bots; each bot is given a unique token which, when appended to the URL, allows users to access the bot's API.


### 3. Issuing Alerts for New IP Address Arrival

As the sole user of this API, any new request from an unfamiliar IP is suspicious and should therefore trigger an alert to me. In order to access the API endpoint, a potential hacker would need to bypass the first two security mechanisms, an unlikely scenario. However, if the unthinkable were to occur and both secret keys were somehow leaked, it should not go unnoticed. I must receive the alert as quickly as possible to curtail the risk. That being said, most of the time it was me using a VPN, causing the alert to be triggered. Thus, I have opted not to block the IP from accessing, but instead simply send an alert.


### 4. Modifying the Default Port

By taking this approach, it mitigates the risk of being scanned by bots, or at the very least, provides me with some time to address any issues should a zero-day exploit occur. Although tailoring the port to be accessible only by my IP could significantly enhance security, it is not feasible in my case, as I frequently connect to a VPN while browsing online. Implementing a proxy could be a solution, but it would also increase my costs, which is not desirable. Given that I deployed my application on AWS EC2, I utilized a security group to allow only specific ports to be publicly accessible, which, in turn, further limited the possible attack surface.


### 5. Initiate/Terminate the Password Manager as Required

This is one of the strategies I've employed to minimize the possibility of cyber attacks, enabling me to rest assured that my password management server has ceased receiving potentially harmful requests from the external world. This method is remarkably effective, as it not only reduces the susceptibility to attacks, but also ensures my immediate reaction in the case of an attack. My implementation involves utilizing the systemd service, where a script gets activated to invoke the aws start-instances/stop-instances command whenever I start or shut down my computer, all configured with the most minimal permissions.


### 6. Install the Monitoring Tool

So far, I've discussed various methods to minimize the attack surface and time. I am confident that the password manager app is quite secure now. However, if the unthinkable occurs and a hacker manages to bypass all protections, either through leaked information or a zero-day exploit, I want to be the first to know. That's why a monitoring tool is crucial to track the app and host for any abnormal behavior.

A typical hacking process involves information gathering, obtaining low privilege shell access, and then escalating to root shell access. During the shell acquisition process, the hacker will probe the system extensively to identify weaknesses. Such activities can be monitored and real-time alerts sent to the administrator.

In my search for a suitable monitoring tool, I discovered Falco, which perfectly meets my requirements. Falco is a robust monitoring tool designed for Linux systems running Docker containers. As it monitors kernel events, it can oversee both the host and Docker containers running on it. It allows for user-customized monitoring rules, and the default rules are notably useful. These rules cover situations such as terminal shell in a container, Netcat Remote Code Execution in a container, untrusted reading of sensitive files, among others. 

I've found Falco to be an impressive tool and since discovering it, I've been learning how to use it effectively. For convenience, I've set up a private Telegram channel dedicated to receiving alerts from Falco.

### 7. Automated Backup



## Compared to My Previous Methods

Prior to discovering Bitwarden, I used LastPass to store my login passwords for various websites. However, employing a customized Bitwarden has greatly enhanced my online safety, as it significantly reduces the potential attack surface. Moreover, Bitwarden gives me the ability to decide when and what to update with my password manager - a degree of control not afforded by LastPass. The introduction of new features into software can sometimes inadvertently create fresh attack surfaces, which hackers may attempt to exploit. Therefore, having a deep understanding of how my password manager operates brings me much greater comfort and peace of mind.

When it comes to private keys, such as wallet keys, I encrypt them locally as a file and then upload them to either Google Drive or AWS S3, both of which have 2FA enabled. I initially relied heavily on Google Drive to store my encrypted keys, but I have been progressively transitioning to AWS S3 for better control over my passwords and keys. I regard both platforms as quite secure. However, as the number of my keys increases, this method has become laborious and inconvenient. In the future, I plan to gradually migrate my less critical keys to a new password manager.

## Future Enhancements

