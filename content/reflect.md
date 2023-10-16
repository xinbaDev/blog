---
Title: "Systematic Reflections on Current Work"
Date: 2022-04-02T20:16:00+11:00
Summary: Having dedicated several years to the IT industry, it's imperative for me to take a comprehensive look back at my professional journey. This article serves as a platform for me to delve into my work over these years, beginning with an exploration of some common interview questions.
draft: True
---

Having dedicated several years to the IT industry, it's imperative for me to take a comprehensive look back at my professional journey. This article serves as a platform for me to delve into my work over these years, beginning with an exploration of some common interview questions.


## Introduction to Business Background

#### Company's main business (business logic, technical difficulties)

The company's primary focus is centered around stock information, encompassing stock prices, news, related financial reports, shareholder information, and paid announcement translations. In addition, the company extends its services to include new stock issuance and fund subscriptions. From a logical standpoint, the business can be dissected into two main components. Firstly, data is aggregated from various sources. Secondly, the data is stored efficiently and presented to users reliably. My role primarily involves the development and operation of backend applications, meaning my technical challenges are mainly concentrated in this realm. More specifically, this involves the efficient and dependable display of data to users in real-time.

## Architecture Evolution

#### How to upgrade the architecture (servers, applications, databases)

We leverage AWS as our cloud service provider. Initially, we operated with only two servers, one for the front-end web and another for the backend API. All APIs were centralized on a single EC2 instance. The backend server was linked to AWS RDS for data access. As our service portfolio expanded, maintaining a single server became unviable. The increasing number of services led to server overload and decreased responsiveness. Moreover, any issues would render the entire website inaccessible, causing significant disruptions. To mitigate these challenges and improve response times, a transition from a single-machine mode to a distributed architecture was imperative.

One of the earliest services to be decoupled was the static file download service, initially provided via an Nginx server. Although Nginx was potent, it had a single point of failure and high storage costs. We later moved PDF files to AWS S3, enhancing reliability and download speeds while reducing storage expenses. S3's intelligent storage tiering offered a balance of performance and cost-effectiveness by automatically migrating less frequently accessed files to slower, cheaper storage.

We also ventured into serverless services, migrating some standalone APIs to Lambda. Lambda's cost-effectiveness, particularly for APIs with infrequent use, was a significant advantage. For instance, the API for email existence verification, though relatively independent, was a prime candidate for Lambda migration.

Finally, we migrated certain services to Kubernetes clusters. Kubernetes proved invaluable in managing virtual containers. The containerization of services streamlined deployment and management. The subdividing of services introduced new challenges, such as monitoring a multitude of containers. This shift prompted us to adopt the Prometheus + Grafana + Alertmanager monitoring stack, providing extensive visibility into our services.

## Understanding the principles of the underlying technologies of the company

#### servers, middleware (caching, message queues), databases, Docker, Kubernetes, and so on.

My initial exposure to server technology was through Nginx. I delved into its C source code and familiarized myself with its structure. Nginx stood out for its asynchronous response model and performance. However, it posed scalability challenges and required recompilation when making configuration changes. Over the years, new extensions and improvements have likely addressed these issues. Nonetheless, Nginx's C-based nature might hinder readability compared to more recent servers written in languages like Go.

Database-wise, I predominantly worked with AWS's RDS databases, particularly Postgresql. RDS simplifies database management, offering features like automatic backup, master/slave architecture, and robust monitoring. AWS's reminders about database security updates proved invaluable. RDS optimizations relieved the need to focus on underlying hardware, enabling me to concentrate on table design, index optimization, and SQL query enhancements.

Redis, a caching middleware, became a favorite tool of mine. It's a resource-efficient open-source caching solution developed in C, renowned for its versatility. Redis supports multiple data structures and delivers rapid response times. Although I primarily use single instances, I have yet to explore its clustering capabilities. To maximize Redis's potential, I've adopted practices like connection pooling and implementing timeout reconnections using exponential backoff.

Docker is another pivotal tool in my arsenal. Initially challenging to learn, it eventually became indispensable. Docker streamlines testing, development, and deployment. It grants me the ability to develop in various environments and ensures seamless deployment, enhancing development and operational efficiency, making it a cornerstone of DevOps practices.

Kubernetes has played a significant role in my recent projects, particularly in the context of service splitting and containerization. My preference lies with the fargate mode of EKS, where AWS handles server management. Configuring servers in advance is unnecessary, and resource allocation is simplified.

Prometheus, Grafana, and Alertmanager have been instrumental in our DevOps endeavors, offering a robust and extensible cluster monitoring solution. These tools facilitate infrastructure and application status monitoring, streamlining operations. Currently, we employ this trio on our Kubernetes cluster for features like pod status notifications.

In the realm of DevOps, Terraform stands as an indispensable tool, enabling infrastructure as code and dramatically reducing maintenance overhead. It shares similarities with Kubernetes, using descriptive YAML files to control infrastructure without requiring in-depth implementation knowledge, streamlining infrastructure management.

## Examination of System Challenges

#### Technical difficulties (what are they, why are they difficult, and how to solve them).

The most formidable technical challenge I've encountered revolved around upgrading and optimizing a GraphQL server application, a problem that vexed me for a considerable duration. Initially, server infrastructure crashes led to persistent CPU overloads and eventual system crashes. Despite my initial assumption that poorly written code was the culprit, closer scrutiny revealed that the code was largely auto-generated, pointing towards framework-related issues. Further investigation revealed that GraphQL queries were generating excessive SQL queries, causing CPU spikes due to database fetches.

To alleviate this, I explored caching solutions, leveraging the Apollo server's caching plugin to reduce the database query load. This solution appeared to resolve the issue for some time. However, it resurfaced, slowing down the system, especially during cache invalidation.

Despite the absence of a system crash, a noticeable decrease in speed, particularly during cache invalidation, signaled the onset of an unsustainable situation. Recognizing the urgency, I committed to a thorough examination of the underlying framework. The framework, written entirely in JavaScript, initially seemed somewhat cumbersome. Following a series of experiments and an in-depth code analysis, I unearthed the root cause of the sluggish performance. In essence, the framework's flexibility inadvertently led to inefficiencies in the conversion of GraphQL queries to SQL queries. This inefficiency resulted in the unnecessary retrieval of data, imposing a dual burden on the database and transmission times while significantly elevating CPU consumption on the server. Equipped with this insight, I implemented targeted measures and placed restrictions on queries. Though this approach did have some side effects, causing certain queries to malfunction, extensive research and testing revealed minimal disruption to existing queries, with few and easily implementable changes. The paramount benefit was that, post-implementation, the system's speed remained unaffected even as the database's data load increased, effectively providing a remedy to the problem. After careful consideration of alternatives, I opted for this approach.