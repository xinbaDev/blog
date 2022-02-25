---
title: "记一次服务器事故以及对架构的一些思考"
date: 2020-02-23T21:30:11+11:00
summary: 在2020.02.20的早上8点半左右有用户报告网站无法访问，8点40分收到通知，赶紧通过手机访问网站确认，主站的前端服务器出了问题。于是紧急通过远程连接登录到aws的云端服务器，发现服务器仍然在运行，排除EC2服务器挂掉的情况。接着查node server， 发现PM2还在运行，但是application已经挂掉。 于是怀疑是硬盘空间不足。一查硬盘空间，果然已经满了。于是马上通过aws的console加空间，然后重启服务器。重启服务器以及相关应用后，服务器于8点49分恢复正常访问。
draft: false
---

在2020.02.20的早上8点半左右有用户报告网站无法访问，8点40分收到通知，赶紧通过手机访问网站确认，主站的前端服务器出了问题。于是紧急通过远程连接登录到aws的云端服务器，发现服务器仍然在运行，排除EC2服务器挂掉的情况。接着查node server， 发现PM2还在运行，但是application已经挂掉。 于是怀疑是硬盘空间不足。一查硬盘空间，果然已经满了。于是马上通过aws的console加空间，然后重启服务器。重启服务器以及相关应用后，服务器于8点49分恢复正常访问。

## 事故的原因分析

为了避免以后出现这种情况，必须弄清楚事故发生的原因。为什么硬盘满了导致服务器挂掉？理论上说，即使没有硬盘空间不够，只要没有写硬盘的操作就不会出错。就算发生了写硬盘，这个异常按道理也不应该导致前端服务器挂掉。到底中间经历哪些过程，操作系统，PM2，服务器应用在这次事故中都扮演的什么角色？

首先让我们回到事故现场：

PM2        | 2020-02-19 17:45:32: --- PM2 global error caught ---------------------------------------------------
PM2        | 2020-02-19 17:45:32: Time                 : Wed Feb 19 2020 17:45:32 GMT+0100 (AEDT)
PM2        | 2020-02-19 17:45:32: Callback was already called.
PM2        | 2020-02-19 17:45:32: Error: Callback was already called.
PM2        |     at /usr/local/lib/node_modules/pm2/node_modules/async/dist/async.js:903:32
PM2        |     at WriteStream.<anonymous> (/usr/local/lib/node_modules/pm2/lib/Utility.js:162:13) 
PM2        |     at emitOne (events.js:96:13)                                                       
PM2        |     at WriteStream.emit (events.js:188:7)                                              
PM2        |     at onwriteError (_stream_writable.js:346:10)                                       
PM2        |     at onwrite (_stream_writable.js:364:5)                                             
PM2        |     at WritableState.onwrite (_stream_writable.js:90:5)                                
PM2        |     at fs.js:2148:14                                                                   
PM2        |     at FSReqWrap.wrapper [as oncomplete] (fs.js:748:5)                                 
PM2        | 2020-02-19 17:45:32: ===============================================================================                     
PM2        | 2020-02-19 17:45:32: [PM2] Resurrecting PM2  
PM2        | Be sure to have the latest version by doing `npm install pm2@latest -g` before doing this procedure.         
PM2        | [PM2] Saving current process list...  
PM2        | Error: EACCES: permission denied, open '/home/ubuntu/.pm2/dump.pm2' 
PM2        |     at Error (native)    
PM2        |     at Object.fs.openSync (fs.js:641:18) 
PM2        |     at Object.fs.writeFileSync (fs.js:1347:33) 
PM2        |     at fin (/usr/local/lib/node_modules/pm2/lib/API/Startup.js:362:14) 
PM2        |     at ex (/usr/local/lib/node_modules/pm2/lib/API/Startup.js:375:30) 
PM2        |     at ex (/usr/local/lib/node_modules/pm2/lib/API/Startup.js:381:16) 
PM2        |     at /usr/local/lib/node_modules/pm2/lib/API/Startup.js:382:9  
PM2        |     at /usr/local/lib/node_modules/pm2/node_modules/pm2-axon-rpc/lib/client.js:45:10
PM2        |     at Parser.<anonymous> (/usr/local/lib/node_modules/pm2/node_modules/pm2-axon/lib/sockets/req.js:67:8)                     
PM2        |     at emitOne (events.js:96:13)  


这是事故发生时候，PM2的log。整个log基本上可以分成两部分。首先第一步是PM2抓到一个全局的错误（没有被处理的异常），接下来第二步触发PM2的resurrecting。在这个过程中，因为/home/ubuntu/.pm2/dump.pm2的permission问题，导致current process  list的保存失败，最终的结果是服务器应用没有被正常重启。permission的问题应该是安装PM2时候没有正确安装导致，这个定时炸弹从服务器安装开始（2年前）一直存在。但是即使permission没问题，因为硬盘空间不足，保存的过程也会失败。

第二步相对容易理解，第一步的全局错误又是怎么产生的呢？

首先这error是async.js抛出来的：

```javascript=
function onlyOnce(fn) {
    return function() {
        if (fn === null) throw new Error("Callback was already called.");
        var callFn = fn;
        fn = null;
        callFn.apply(this, arguments);
    };
}
```

这个函数的作用就是保证callback只被运行一次，如果出现多次运行，或者传入null，都会触发异常抛出，由调用者来处理这个异常。这个函数会被在async中waterfall的函数调用：


```javascript=
var waterfall = function(tasks, callback) {
    callback = once(callback || noop);
    if (!isArray(tasks)) return callback(new Error('First argument to waterfall 
    must be an array of functions'));
    if (!tasks.length) return callback();
    var taskIndex = 0;

    function nextTask(args) {
        var task = wrapAsync(tasks[taskIndex++]);
        args.push(onlyOnce(next));
        task.apply(null, args);
    }

    function next(err/*, ...args*/) {
        if (err || taskIndex === tasks.length) {
            return callback.apply(null, arguments);
        }
        nextTask(slice(arguments, 1));
    }

    nextTask([]);
};

```

这个waterfall是作用是异步的运行所有tasks，而tasks是an array of functions，由调用者传入。
而waterfall函数又被PM2的startlogging调用：

```javascript=
startLogging : function(stds, callback) {
    /**
     * Start log outgoing messages
     * @method startLogging
     * @param {} callback
     * @return
     */
    // Make sure directories of `logs` and `pids` exist.
    // try {
    //   ['logs', 'pids'].forEach(function(n){
    //     console.log(n);
    //     (function(_path){
    //       !fs.existsSync(_path) && fs.mkdirSync(_path, '0755');
    //     })(path.resolve(cst.PM2_ROOT_PATH, n));
    //   });
    // } catch(err) {
    //   return callback(new Error('can not create directories (logs/pids):' + err.message));
    // }

    // waterfall.
    var flows = [];
    // types of stdio, should be sorted as `std(entire log)`, `out`, `err`.
    var types = Object.keys(stds).sort(function(x, y){
      return -x.charCodeAt(0) + y.charCodeAt(0);
    });

    // Create write streams.
    (function createWS(io){
      if(io.length != 1){
        return false;
      }
      io = io[0];

      // If `std` is a Stream type, try next `std`.
      // compatible with `pm2 reloadLogs`
      if(typeof stds[io] == 'object' && !isNaN(stds[io].fd)){
        return createWS(types.splice(0, 1));
      }

      flows.push(function(next){
        var file = stds[io];
        // if file contains ERR or /dev/null, dont try to create stream since he dont want logs
        if (!file || file.indexOf('NULL') > -1 || file.indexOf('/dev/null') > -1)
          return next();
        stds[io] = fs.createWriteStream(file, {flags: 'a'})
          .on('error', function(err){
            next(err);
          })
          .on('open', function(){
            next();
          });
        stds[io]._file = file;
      });
      return createWS(types.splice(0, 1));
    })(types.splice(0, 1));

    async.waterfall(flows, callback);
  },

```
通过阅读源码，可以发现flows就是waterfall异步运行的tasks。而根据pm2 的log, 导致出现异常的地方就是在createWriteStream中处理异常的next(err)所触发。createWriteStream触发异常好理解，因为硬盘不足。但是next是什么呢，经过分析，next正是onlyOnce(next)。简单得讲，waterfall中运行onlyOnce(next)这个callback,   在运行中出现异常，导致再次运行onlyOnce(next)！ 如果没有看懂，可以看看这个简化版的issue： https://github.com/caolan/async/issues/1611

分析到这里整个事故过程就比较清楚了。首先是PM2在logging的时候，因为空间不足抛出异常，而这个异常又触发async中的异常。PM2没有考虑到这种异常的情况，并没有处理，导致resurrect。


在测试过程当中，我发现最新的PM2并没有这个bug，一查其实这个bug已经在这个[commit](https://github.com/Unitech/pm2/commit/374f88ba0af02f679888fce4496c183a45b9cfd7#diff-92c9bcfa02228bd9e146b5178ac63dd8)中被fix了。PM2的处理方式是catch这个异常，然后通过console安静地把异常显示出来，不让其成为一个全局的异常导致服务挂掉。


## 事故总结以及未来架构的设想

发生这种事故有多方面的原因，硬盘空间不足是导火索。如果硬盘空间充足不会触发这个PM2这个bug。如果PM2有合理处理这个异常，硬盘空间不足不会引起服务器挂掉。这个事故给我们的启示是，并不是所有library都是可靠的。在使用所有libaray的时候都要assume他不可靠。连PM2这种被多年广泛使用的PRODUCTION GRADE的应用都存在bug，何况是其他程序。错误一定是会发生的，我们能做的就是通过好的架构，避免这中错误带来的影响。前端服务器的架构一直用最开始的一个node server打天下，存在单点故障的问题，而且没有监控，导致不能提早发现预防。存在相同问题的还有财经服务器，cms服务器。

这次事故也让我反思，如果我们的一个后端服务，例如api服务器挂了，我有没有办法尽量减少他的影响。好的架构应该能够减少事故出现的机率，也能减少事故造成的影响。我的想法是尽量分离不相关的业务逻辑到不同的服务器上。其实一开始后端服务器也和前端服务器一样，一台服务器单打独斗。后来我意识到这个问题，开始慢慢把新功能都分散到不同的服务器上。但是仍然做的不够。如果现在主站的最主要的API服务器挂掉，那么网站的大约50%的内容仍然会受到影响。分离这些业务逻辑除了减少事故发生的影响，还有个好处，那就是可以根据不同的业务需求和特点来合理分配资源。

比如对于前端服务器，其本身的特点是大部分都是读取，基本上都是传输html,js等静态文件，只有一些服务器渲染的内容需要动态生成。这时就适合把相对静态的部分放到CDN上。之前图片已经放在CDN上了，但是其实连html页面，js，css这些相对静态的内容也应该放到CDN上。

具体来说，目前前端的服务主要可以分为两类，一种是相对静态的资源（主页html，js，css等），另一种是相对动态的内容，涉及服务器渲染的部分。其中相对静态的部分可以放在s3上，然后通过cloudfront去访问，而需要服务器渲染的部分还是可以继续放在原来服务器上，但是请求需要先经过cloudfront，通过cloudfront去server获取资源。cloudfront可以设置监控，当cloudfront获取资源失败，可以发送邮件或者短信通知，而不是等用户回报。（其实还可以做多点部署来进一步减少事故的可能性，目前后端的服务已经开始使用kubernetes来进行多点部署，但是对于前端服务，要改动的地方可能会较多）。这样可以实现这部分静态资源的高可用，提高服务的健壮性。这样即使出现服务器单点故障，虽然动态渲染的部分仍然会受到影响，但是通过主网址访问的用户仍然能看到网页，不会出现什么都看不到的情况。

架构的简单设想图

![](https://i.imgur.com/OtS5oFT.png)

当然任何涉及到架构的改动都是有风险和成本的。但是通过这两天（周四，周五）的调研和实验，我们已经在staging上初步实现了cloudfront的中间代理，这让我相信这个架构的迁移是可以实现的，而且成本应该也是相对较小的。