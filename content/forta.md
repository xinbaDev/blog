---
title: "Forta contest"
date: 2022-06-08T19:39:11+11:00
summary: Before discussing the Forta competition, let me introduce Forta first. So far, Forta has been developed for about a year, with a total of 1330 commits, and the main developers are two people. The development language is GO. This is not a particularly large project, and its functions are relatively clear. It is mainly used for monitoring. In addition, GO is inherently a highly engineering-oriented language, so reading it is not too difficult.
draft: false
---

## Introduction

Before discussing the Forta competition, let me introduce Forta first. So far, Forta has been developed for about a year, with a total of 1330 commits, and the main developers are two people. The development language is GO. This is not a particularly large project, and its functions are relatively clear. It is mainly used for monitoring. In addition, GO is inherently a highly engineering-oriented language, so reading it is not too difficult.

First, I started by looking at the latest commit on the master branch and went through the code structure of the entire project, to understand the main code components. Especially for some interesting functional code, such as the part that captures blockchain data, I will specifically go and look at it.

After completing this step, if I am still interested in the project or if there are some things that I still don't understand, I will start from the first commit to understand how the architecture of the project was gradually built up. For the Forta project, I probably looked at hundreds of commits, mainly focusing on some commits involving important functions. I generally skipped over bugfixes and refactorings.

After completing this step, I have a fairly good understanding of Forta's architecture. Finally, I went back to look at the latest commit and integrated all the scattered understandings of what I had previously seen. At this point, because I have a comprehensive understanding of the code framework, I can delve into some of the code details. Because my goal is to modify the code to make it run locally, I mainly focus on a few issues, such as how the agent is registered, how to configure the local agent, and how alerts are sent.

## Forta Workflow and Main Components

To start Forta, Docker must be installed first. Forta heavily relies on Docker, and all components are run through Docker containers, including the agent. The components communicate with each other through gRPC, and the communication protocol code was initially in the Forta node's repository but later separated into another repository called Forta-core-go.

Before starting Forta, there are two main steps. First is "forta init," which generates a configuration file in the ".forta" directory. Second is "forta register," which registers the scanner to the chain's registry contract so that the scanner can be discovered and assigned to an agent by the assigner software (which is not open source). This step is not necessary for running Forta on a single machine.

Once these steps are completed, Forta can be started with "forta run." The first component to start is the supervisor, which monitors a series of containers that need to be running. After the supervisor starts, it launches other components, including the IPFS container, NATS container, JSON-RPC container, and scanner container. The scanner container is the main component of Forta because it contains most of the workflow logic.

When the scanner starts, it initializes several services such as the agent pool, alert sender, and registry service. The registry service polls the scanner contract on the chain to update the agents in the agent pool. The scanner is the most critical component of Forta, and all other components are more or less linked to it. Its workflow can be summarized as follows:

The scanner fetches block data by polling, and multiple workers process transactions in the block. The workers send the transactions to the analyzer through channels, and the analyzer converts the transactions to requests using the EvaluateTxRequest protocol. The analyzer sends the requests to all the agents through the agent pool. The agents process the transactions by invoking a remote bot method (through gRPC) and send the results to TxResults. The analyzer then processes the results and sends the findings to the alert sender. Finally, the alert sender batches the alerts and sends them to an alert server, which is not open source, and only a mock test is available.If you want to run Forta on a single machine, you need to modify and complete this part of the process.

## Some thoughts on the architecture of Forta

I really appreciate the architecture of Forta, especially how it separates the agent and scanner, with each agent running separately in a Docker container. Previously, I wrote a monitoring tool using the GO language, but all the features were bundled together, making it difficult to extend and maintain. Of course, achieving the architecture of Forta is not easy. First, a protocol needs to be specially written for communication between the agent and scanner, which increases the difficulty of programming. Secondly, a distributed architecture also places higher demands on the monitoring of the program itself. A distributed architecture like Forta's (especially since it involves smart contracts) is still relatively rare for me. For example, it's not often that data is stored on the blockchain while some data is stored locally. The last similar distributed project I saw was Nym (which is more complex than Forta because it implements the functionality of a blockchain, and is written in Rust, which I'm not yet familiar with). By tracing the code of Forta, I found that it was originally a project developed internally by the OpenZeppelin team. The project went through several name changes and evolved into what it is today. Learning about the evolution of the architecture through improving the code of Forta is like reading a book that slightly exceeds my understanding level, which is very rewarding.


## forta contest

Recently, Forta officially launched, and its tokens are now freely traded. Additionally, a bot development competition was held recently (https://docs.forta.network/en/latest/contest7-forta/). Winners can receive token rewards ranging from $500 to $4000. Actually, Forta has held several similar competitions before, but I didn't notice them until this one. The results of the competition were just announced a few days ago, and three winners were selected and their related open-source code was published, so I plan to make a special note of it.

First of all, the content of this competition was to develop a bot that can not only detect on-chain attacks but even detect them before they happen. This is a big challenge, and for this purpose, Forta shared a case study about Saddle Finance, which is a great blog post, especially for those interested in on-chain monitoring. The evaluation criteria for the competition were mainly based on bot implementation, testing, and documentation, such as whether the bot can correctly alert, code readability, test quality (positive/negative tests), and the quality of documentation.

After discussing the competition content and evaluation criteria, let's talk about the winning bots. I have looked at the code for all three winning bots, and I will analyze them according to the evaluation criteria:

In terms of functionality, all three bots meet the requirement of being able to detect attacks in advance, and they use similar techniques. They fork a local blockchain and use fuzzing to hit functions. If the transaction is successful, they detect whether there is a large quantity change in common tokens and send an alert. The difference is that the fuzzed functions are different, some can test functions with up to 5 parameters, and some can do multiple rounds of fuzzing. Without a deep understanding of function execution on the Ethereum blockchain, it is impossible to write such code. In addition to different fuzzing techniques, the first-place bot also detects tornado funding and suspicious contract creation to increase the accuracy of alerts. In terms of code readability, the first-place bot is also more readable than the other two. In terms of testing, the first-place bot has the most and highest quality tests. However, in terms of documentation, the documentation for the first-place bot is slightly weaker. Overall, the first-place bot is well-deserved.

Analyzing the winning bots is not the focus of this record; I mainly want to record some of my thoughts on bot development. Actually, I had thought about how to implement this bot before, but at that time, I didn't think about local forking. Instead, I thought about passing messages between agents to filter out possible attacks step by step, first listening to tornado funding, then suspicious contract creation, and finally locating the attack. Unlike the first-place bot, this method does not need to send an alert at the tornado funding stage, thereby increasing accuracy. However, according to my understanding of Forta's current architecture, agents cannot communicate with each other, unless one develops an API to receive and provide relevant data. However, this does not meet the requirements of this bot's development, and it is also troublesome to develop. Although Forta currently supports combining alerts for multiple events, it is achieved through the graph API (for this purpose, I even looked up the code for the graph node, and maybe I can write a separate record about it later). I don't really like this method. I believe that agents' ability to call and communicate with each other is more natural and flexible. Maybe I can develop a local version of Forta for my personal use later.

This competition did teach me a lot of on-chain monitoring techniques, especially fuzzing, which I hadn't thought of before and found very interesting. My feeling is that although fuzzing can detect attacks in advance, it is very easy to bypass. The three winning bots, as long as the attacker is a little prepared, can easily bypass and render fuzzing completely ineffective. Currently, other monitoring methods are still needed, such as monitoring tornado funding events. And using the current architecture may not be the best for fuzzing, so a clustered approach should be used locally.