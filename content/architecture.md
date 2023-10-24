---
Title: "An incident with a server and some thoughts on architecture"
Date: 2020-02-23T21:30:11+11:00
Summary: On the morning of February 20th, 2020, at 8:40am, I received a notification that the website was inaccessible. I quickly logged in and found that the frontend server of the main site was having issues. I urgently connected remotely to the AWS cloud server and found that the server was still running, ruling out the possibility of the EC2 server crashing. I then checked the Node server and found that PM2 was still running, but the application had crashed. I suspected that the hard drive was full. Upon checking the hard drive, it was indeed full. I immediately added space through the AWS console and restarted the server. After restarting the server and related applications, the server was back to normal at 8:49am.
draft: true
---

On the morning of February 20th, 2020, at 8:40am, I received a notification that the website was inaccessible. I quickly logged in and found that the frontend server of the main site was having issues. I urgently connected remotely to the AWS cloud server and found that the server was still running, ruling out the possibility of the EC2 server crashing. I then checked the Node server and found that PM2 was still running, but the application had crashed. I suspected that the hard drive was full. Upon checking the hard drive, it was indeed full. I immediately added space through the AWS console and restarted the server. After restarting the server and related applications, the server was back to normal at 8:49am.
## Analysis of the Cause of the Accident

In order to avoid such situations in the future, it is necessary to understand the cause of the accident. Why did the server crash due to a full hard drive? Theoretically, even if there is not enough hard disk space, as long as there is no operation that writes to the hard disk, there should be no error. Even if there is a write to the hard disk, this exception should not cause the front-end server to crash. What processes, operating systems, PM2, and server applications were involved in this accident?

First, let's go back to the scene of the accident:

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


This is the log of PM2 at the time of the accident. The entire log can be divided into two parts. The first step is that PM2 catches a global error (unhandled exception), and the second step triggers PM2's resurrecting. During this process, due to permission issues with /home/ubuntu/.pm2/dump.pm2, the saving of the current process list fails, resulting in the server application not being restarted properly. The permission issue should have been caused by incorrect installation of PM2, and this time bomb has existed since the installation of the server (2 years ago). Even if there is no permission problem, the saving process will fail due to insufficient disk space.

But how was the global error in the first step generated?

Firstly, this error was thrown by async.js.

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

The purpose of this function is to ensure that the callback is only executed once. If it is executed multiple times or null is passed in, an exception will be thrown, which the caller should handle. This function will be called in the async waterfall function.

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

The function of this waterfall is to asynchronously run all tasks, where tasks are an array of functions passed in by the caller. The waterfall function is then called by PM2's startlogging function.

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
By reading the source code, we can discover that flows are tasks that run asynchronously in a waterfall. According to the logs of PM2, the place where the exception occurred was triggered by next(err) handling in createWriteStream(). It's easy to understand that createWriteStream() triggers an exception because of disk space. But what is next? After analysis, next is actually onlyOnce(next). In simple terms, while running the onlyOnce(next) callback in the waterfall, an exception occurs, which causes onlyOnce(next) to run again! If you don't understand, you can check out this simplified issue: https://github.com/caolan/async/issues/1611.

Analyzing up to this point, the whole incident process becomes clearer. Firstly, when PM2 is logging, an exception is thrown due to insufficient space, and this exception triggers an exception in async. PM2 did not consider this type of exception and did not handle it, resulting in a resurrection.


During the testing process, I found that the latest version of PM2 did not have this bug. Upon investigation, I discovered that this bug had actually been fixed in this [commit](https://github.com/Unitech/pm2/commit/374f88ba0af02f679888fce4496c183a45b9cfd7#diff-92c9bcfa02228bd9e146b5178ac63dd8). PM2 handles this issue by catching the exception and then quietly displaying it through the console, preventing it from becoming a global exception that could cause the service to crash.


## Summary of the accident and ideas for future architecture

There were multiple factors that caused the accident, and insufficient hard disk space was the catalyst. If there was enough disk space, the PM2 bug wouldn't have been triggered. If PM2 had handled this exception reasonably, insufficient disk space wouldn't have caused the server to crash. The lesson we learned from this accident is that not all libraries are reliable, and when using any library, we should assume that it is unreliable. Even PM2, a widely used production-grade application for many years, has bugs, not to mention other programs. Errors are bound to happen, and what we can do is to avoid the impact of these errors through good architecture. The front-end server architecture has been using the same node server since the beginning, which has a single point of failure and no monitoring, leading to the inability to detect and prevent it in advance.

This accident also made me reflect on whether I could minimize the impact if one of our backend services, such as the API server, went down. Good architecture should be able to reduce the likelihood of accidents and the impact they cause. My idea is to try to separate unrelated business logic into different servers as much as possible. Initially, the backend server was like the front-end server, a single server fighting alone. Later, I realized this problem and gradually dispersed new features to different servers. But I still didn't do enough. If the main API server of the website goes down now, about 50% of the content will still be affected. Separating these business logics not only reduces the impact of accidents but also has the advantage of allocating resources reasonably according to different business needs and characteristics.

For example, for the front-end server, most of its features are reading, basically transmitting static files such as HTML and JS, and only some server-rendered content needs to be dynamically generated. This is suitable for putting the relatively static part on the CDN. Previously, the images were already on the CDN, but even relatively static content such as HTML pages, JS, and CSS should also be placed on the CDN.

Specifically, the current front-end service can be mainly divided into two categories: relatively static resources (homepage HTML, JS, CSS, etc.) and relatively dynamic content involving server rendering. The relatively static part can be placed on S3 and accessed through CloudFront, while the part that needs server rendering can still be placed on the original server, but the request needs to go through CloudFront to obtain resources from the server. CloudFront can be monitored, and when it fails to obtain resources, it can send email or SMS notifications, instead of waiting for users to report it. (In fact, multiple deployments can be made to further reduce the possibility of accidents. The backend service has begun to use Kubernetes for multiple deployments, but there may be more changes to be made for the front-end service). This can achieve high availability of these static resources and improve the robustness of the service. Even if there is a single point of failure on the server, users who access through the main URL can still see the website, and there will be no situation where nothing can be seen.

Simple architectural diagram

![](https://i.imgur.com/OtS5oFT.png)
