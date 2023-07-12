---
Title: "How Chatgpt helps me create a game text extractor and teach me japanese"
Date: 2023-05-04T23:15:32+11:00
Draft: false
Summary: Recently, I have been playing a game called “The Legend of Heroes - Trails of Cold Steel,” a JRPG that I hope can help me learn some Japanese. I ended up creating a game text extractor to make it easier for me to translate the in-game text. When combined with ChatGPT, it becomes a very helpful Japanese language teaching app. I can’t help but record what I have learned during this process.
---

Recently, I have been playing a game called "The Legend of Heroes: Trails of Cold Steel," a JRPG that I hope can help me learn some Japanese. I ended up creating a game text extractor to make it easier for me to translate the in-game text. When combined with ChatGPT, it becomes a very helpful Japanese language teaching app. I can't help but record what I have learned during this process.

## Motivation

It all began with a YouTube channel I stumbled across called "Game Gengo," which focuses on learning Japanese through playing games. I have wanted to improve my Japanese for quite some time. After watching the channel, I realized that I enjoy playing RPG games, so I thought it wouldn't be a bad idea to give it a try. I picked up a few JRPG games that interested me on Steam and gave it a shot. However, I soon found it quite difficult to enjoy the game if I had to constantly check the meaning of every word I encountered. I needed to make the learning process as easy as possible for myself. To achieve that goal, I needed to find a way to extract the text from the game instead of manually typing every single word into Google Translate. My initial thought was to create a program to extract the text from memory. But in order to do that, I needed to know the exact address of the text in memory. Knowing the address alone was not enough since it would change every time the game restarted. I needed to find a base address that could lead me to it.

## Journey

Although I had experience using cheat engine and had successfully created a program to modify money/stats in a similar game before, I had no experience in extracting text from any game whatsoever. The process turned out to be more challenging than I initially thought. I spent hours experimenting and playing with cheat engine just to find a base address that would allow me to locate the text address. During this process, I also learned to read some of the assembly code that I was not familiar with. Thanks to ChatGPT, the process became somewhat enjoyable as it explained the assembly code quite well when I presented it with the code. If it weren't for ChatGPT, this process would have been more tedious and frustrating. Eventually, I located the address of the text in memory, and I was quite happy about what I had achieved and learned during this process. ChatGPT really made it enjoyable for me.

After successfully extracting the text from the memory, I decided to take one step further. Why not let ChatGPT be my Japanese teacher and teach me the Japanese sentences in the game? I asked ChatGPT to imagine itself as my Japanese teacher and help me break down each Japanese sentence I sent, teaching me any grammar and vocabulary used. Once again, ChatGPT delivered as I expected. It was really helpful, as it made the learning process more enjoyable and saved me tons of time searching online by myself. With its help, I managed to learn a great deal of Japanese while still enjoying the game. This wouldn't have been possible before. I can't praise enough how good ChatGPT has been in helping me learn Japanese.

## Make it speak

The game I played was quite old and did not have voice actor speaking in most of the time. This was quite disappointing as I wanted to improve my Japanese listening skill as well. After spending some time on searching for a solution, it turned out there was already an open source project that did that! The project which had an interesting name [ChatWaifu](https://github.com/cjyaddone/ChatWaifu/tree/main) was powered by ChatGPT with Moegoe TTS. It did not take long for me to implement my own version and tried it out. The result was great! When there was not voice actor speaking, I can still hear the AI-generated voice, which sounds like that of a native speaker, with just a click of a button.

## How it helped me create the GUI

When creating the tools to extract the text, one of the challenges I faced was developing a visual interface, a GUI, to help me use it easily. Although I was aware of some libraries, such as Tkinter, that could assist me in creating it, I had no prior experience using them. Learning new tools and techniques is what a programmer should do in their daily life, but it would take quite some time given I have no prior experience. Moreover, if I wanted to create an elegant interface, it would undoubtedly require a lot more time to tweak it. This is where ChatGPT came to the rescue. With its help, I could create an elegant interface that suited my needs in no time. Although it's not perfect, I was satisfied with what I had achieved with the help of ChatGPT in the relatively short time I had spent.

### how it looks like before

![](https://i.imgur.com/zG3HsH7.jpg) 

### how it looks like with the help of Chatgpt

![](https://i.imgur.com/YXehBWF.png) 

## Final thoughts

ChatGPT is astonishingly powerful, and my feelings towards it are mixed. On one hand, I am excited about the potential ways it can help me. I have already experienced firsthand quite a few times, both in my work and in my life. I've grown to depend on it more and more. On the other hand, I feel threatened by its potential and fear that I might eventually lose my job because of it. I believe this feeling is not unique, and anyone who uses ChatGPT should realize that we are close to the era of AI, if not already in it.