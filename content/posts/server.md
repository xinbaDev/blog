---
Title: "Investigating Open Source Servers"
Date: 2022-07-13T19:45:00+11:00
Summary: Recently, due to work requirements, I have been delve into distributed tracing. After reading a series of documents, I planned to deploy a set of distributed monitoring systems to solve the strange connection reset error that has been occurring with WebSockets. After some research, I found that the current nginx server being used does not have good support for this feature, so I decided to simply switch to a different server.
draft: false
---

Recently, due to work requirements, I've had to delve into distributed tracing. After reading a series of documents, I planned to deploy a distributed monitoring system to resolve the strange "connection reset" errors that have been occurring with WebSocket. However, upon further research, I discovered that the current nginx server we're using doesn't fully support this functionality, so I decided to switch to a different server. Actually, I had been considering replacing nginx for some time because, although it boasts excellent performance, it's written in C and configuring it and adding extensions is not very user-friendly. For instance, adding distributed monitoring is not a straightforward task. Furthermore, there are other inconvenient aspects, such as Dropbox's account of their [reasons for and process of replacing nginx]((https://dropbox.tech/infrastructure/how-we-migrated-dropbox-from-nginx-to-envoy)). In summary, nginx is not very easy to maintain. 


## cabby

So I started investigating the current mainstream open-source servers. I remembered encountering a server developed with Golang before, which seemed to have a good overall reputation, and Golang is known for its high concurrency, making it well-suited for server scenarios. Since I am also familiar with Golang, I narrowed my search down to some servers developed in Golang. Soon, I found some nginx alternatives, including several developed in Golang, such as Caddy and Traefik. After comparing them, I felt that Caddy was the most promising one, not only because of its powerful functionality but also because it supports dynamic configuration. Most importantly, it supports OpenTelemetry, which I checked and found that Traefik still does not support well. After roughly understanding Caddy's design ideas and architecture, I quickly became interested in it. Moreover, the code base seems small, with just over 1000 commits, most of which are module code, and there are even fewer core code. So I decided to start reading Caddy's code, especially to understand the code for distributed monitoring.

However, I quickly discovered that Caddy is not easy to read. The part on distributed monitoring is relatively simple, as long as you understand the rough working mechanism of OpenTelemetry and how to use it, you can easily understand it. But the core part of Caddy's code is more difficult to understand. Perhaps I am used to function declarations with clearly defined types, but in Caddy, you often see functions that return variables of type interface{}, which looks unfamiliar. There are also some particularly long functions that appear tiring, and you can see function naming like XXXandXXX. According to the single responsibility principle, this function should be able to be split into two functions. I remember that some variable names were not standardized, and there were cases where they were too short, unclear in meaning, or inconsistent. Overall, the quality does not seem great. Caddy has some unique designs and features, which are quite interesting, so despite some inconvenience in reading it, I still want to give it a try.

Caddy has some distinctive features, such as supporting dynamic configuration using JSON. Specifically, it can easily use a JSON document to configure it in real-time through API calls. In Caddy, the LoadModule function will convert the JSON into an instance in memory through unmarshalling. The benefit of this design is that there is no need to write a complex parser to handle dedicated configuration files, and there are already many existing libraries that can convert configuration files to module instances. However, the drawback of using JSON is that when the JSON configuration increases, the indentation also increases, and it cannot be managed separately but rather must be kept in one JSON file, which looks tiring and is not convenient to maintain. Therefore, Caddy also provides a dedicated configuration format called Caddyfile, which is more suitable for human use.

Another characteristic feature of Caddy is its modular architecture. Caddy's modules are very flexible, with each module having its own life cycle, including load phase, provision/validation phase, use phase, and cleanup phase. A module may also contain submodules. When a module is imported, the init function in the module is triggered, and then the module is registered using the RegisterModule function. Thanks to this modular system, new functionality can be easily added through modules. Caddy has many modules, with the most important being the caddyhttp and tls modules, which were also the first two modules added. caddyhttp is probably the most core and important module in Caddy, mainly responsible for handling HTTP requests. However, tls is one of Caddy's main selling points, primarily addressing the functionality of managing TLS links and certificates. Managing certificates is quite cumbersome, especially when dealing with multiple servers that need to be updated every few months. Using the most commonly used free Let's Encrypt certificates as an example, they need to be updated every three months. Although this can be automated using Certbot, it still requires reconfiguration for each new server added, which can be quite troublesome. In addition, for some internal servers that do not have external ports, each certificate update requires opening a port; otherwise, automatic updates will fail. Caddy's tls module can solve this problem.

Overall, Caddy is powerful and can provide almost all the functionality I need, including load balancing/reverse proxying, rate limiting, websockets, TLS, monitoring, etc., and is easy to extend. According to the Caddy website, Caddy has been running on production servers for a while and can be considered a battle-tested product. Another attractive aspect of Caddy is that its main components have almost no external dependencies, which reduces maintenance costs. However, I still have some reservations about Caddy, mainly because the impression it left me when reading the code was not very good, and in terms of performance, Caddy still lags behind Nginx. In addition, in terms of security, Nginx has a smaller attack surface and has been battle-tested for many years with few security incidents, while Caddy is relatively young and its security cannot be compared to Nginx. In addition to the open-source free version, Caddy also has a commercial version, and it seems that the author has put a lot of effort into the commercial version, which also makes me hesitant to use Caddy. In short, it is a backup option, and I will continue to look at other options.


## sozu

"Sozu" is a reverse proxy written in Rust, and it is the second open source code project that I decided to investigate and learn about after "Caddy". After looking at "Caddy", I suddenly wanted to check if there was an alternative to "nginx" in the Rust ecosystem. The characteristic of Rust is that it does not have a garbage collector, which can avoid the speed fluctuations caused by garbage collection in other language servers.Furthermore, Rust's language features provide higher memory-related security compared to other programming languages.So, I spent some time searching, and the preliminary result is that I did not find a particularly mature project that can completely replace "nginx", let alone meet my requirements. However, I still found a very promising reverse proxy, "Sozu".

When I first saw "Sozu", I was mainly attracted by its architectural design. Its main/worker separation architecture reminded me of the architecture design of "nginx". A server is responsible for accepting and then distributing to multiple separately running worker processes through load balancing algorithms. Moreover, the worker is also single-threaded and uses event loops to asynchronously process data. This architecture design gave me a lot of good impressions, and made me have a lot of expectations for the performance of "Sozu" using the same architecture. Then "Sozu" also supports dynamic configuration, which can be modified without restarting. Moreover, what is more unique is that "Sozu" supports fine-grained configuration modification, such as adding/removing a backend server, adding/removing a certificate, which can refine the processing of different configuration modifications. It is worth mentioning that high reliability is also a major goal of the architectural design of "Sozu", and even the service will not be interrupted during binary upgrade. These features are useful functions that "nginx" did not have.

Out of curiosity, I looked at its code, mainly the parts that interested me, such as how the worker and main communicate, how the worker starts, and how the dynamic configuration and upgrade processes work. My initial feeling was that the code quality was higher than "Caddy" and relatively easy to read. This is mainly reflected in the fact that the code I want to see is relatively easy to find and the overall code structure is clear. However, there are also some parts that I don't like, such as some functions being too long and too wide, no "fmt", and some functions even have more than a dozen parameters, which affects readability. The overall feeling of the code is that it is still being iterated. It should be said that the amount of code for the entire project is actually small, but there are more than 4,000 commits, which is three times that of "Caddy". However, the functionality is still less than that of "Caddy". It can be seen that "Sozu" has made many changes to the existing code.

Overall, my impression of "Sozu" is good, reminding me of some excellent architectural designs of "nginx". Even some of its designs for dynamic configuration through command remind me of "Kubernetes". Currently, "Sozu" is still in continuous development and there are plans to integrate it into the ecosystem of "Kubernetes" as a gateway. Sozu" was initially an internal project of "Clever Cloud" company and later open-sourced. The initial design requirements were more focused on reliability and dynamic configuration, but there was no modularity. Compared with "Caddy", "Sozu" is more like a dedicated reverse proxy, and it is not clear how extensible it is, but currently, there do not appear to be many modular functionalities.

Overall, "Sozu is an interesting reverse proxy that reminded me of the time when I used to read "nginx" code. However, I would not choose "Sozu" as a replacement for "nginx", at least not yet. Although the ability to modify configurations in a fine-grained way through commands is useful, it would be too troublesome to implement every configuration.


## traefik

After spending some time looking at Traefik's code, and I have to say that the quality of Traefik's code is better than what I have seen in Caddy and Sozu. This is not surprising as Traefik is a big project. Although I have only looked at the first few hundred commits, I can already tell that the code quality of Traefik is noticeably better than some similar projects I have seen before. The most important thing is that it is easy to read. The overall code is very pleasant to read, thanks to the frequent code refactoring done by the main contributors. The code architecture looks natural, commits appear to be logical, and simple commit messages make it easy to understand what each commit is about. These are all signs of good code readability.

Traefik also has some features that exceed those of Caddy and Sozu. It not only supports dynamic configuration but also supports circuit breakers, retries, websockets, reverse proxy/load balancing, and many other features I need. As a reverse proxy, the biggest selling point of Traefik is automatic updating of routes and related configurations. To achieve this feature, Traefik provides many providers, including the most commonly used file provider, which directly reads the configuration from a file, and a provider that reads Kubernetes services to form the relevant configuration. This feature is very useful, especially in a microservices architecture, where this automatic discovery and configuration feature is almost a must-have and is the most natural.

In terms of performance, Traefik also performs well, although it is not as fast as Nginx, the difference is not significant. According to benchmarks found online, Traefik's maximum requests per second is about 85% of Nginx's. Considering Traefik's supported features and very convenient automatic dynamic configuration, I think it is completely worthwhile to switch from Nginx to Traefik. The next problem is to learn how to configure Traefik. For example, with the file provider, Traefik uses a different approach than Caddy and has a special parser for handling configuration file reading. This method is not as convenient as Caddy's, but it is more suitable for Traefik, which needs to grab the configuration.

Previously, when I did a preliminary investigation, I thought Caddy might be more suitable because it supports OpenTelemetry and Traefik does not. But after spending more time with traefik, I found that Traefik also supports Jaeger in distributed tracing, and when I read the Jaeger code before, I found that it already supports OpenTelemetry. So this is not a problem anymore. Overall, Traefik is more attractive than Caddy. Although the two have many overlapping features, Traefik is more like a specialized reverse proxy, while Caddy can also be a server, such as a static server.

Traefik is a big project that has been developed since 2015 and has not stopped for seven years. Currently, it has a total of 4,400+ commits and over 600 contributors, and a very active open-source community. My impression of Traefik is good, and I hope to spend more time looking at its code and trying to replace the staging Nginx server with Traefik.