---
title: "strapi-cms中graphql插件优化的一些探索"
date: 2022-05-13T11:18:22+11:00
draft: false
summary: 最近cms服务器又亮红灯了。虽然过去一年以来已经做了各种优化，比如增加缓存，减少对db的访问等，但是都只是短暂缓解，等资料量继续增加，问题又重新浮现。比如缓存失效后，一段时间内服务器会不堪重负，导致响应变慢，甚至当机。为了解决这个问题，前段时间把cms迁移到kubernetes上，使用多点部署，提高可用性。从用户体验上肯定会好很多，但是问题没有真正的解决，每天依然会有服务器变慢，甚至导致重启，而且因为autoscale费用提高等问题。我可以通过增加服务器的配置来减少这方面问题，但这样就又回到老路。必须要从代码层面进行优化了。

---

最近cms服务器又亮红灯了。虽然过去一年以来已经做了各种优化，比如增加缓存，减少对db的访问等，但是都只是短暂缓解，等资料量继续增加，问题又重新浮现。比如缓存失效后，一段时间内服务器会不堪重负，导致响应变慢，甚至当机。为了解决这个问题，前段时间把cms迁移到kubernetes上，使用多点部署，提高可用性。从用户体验上肯定会好很多，但是问题没有真正的解决，每天依然会有服务器变慢，甚至导致重启，而且因为autoscale费用提高等问题。我可以通过增加服务器的配置来减少这方面问题，但这样就又回到老路。必须要从代码层面进行优化了。

目前的cms使用的是strapi-cms框架，版本是v3-beta, 其中使用到了graphql的plugin。在这之前其实我就已经有代码方面优化的探索。首先通读了一遍app的代码，也和编写代码的同事讨论这块，最后得出的结论是应用变慢是框架的问题。于是开始阅读框架的代码，尤其是graphql plugin这块。这才有后来我给graphql加上了cache。还有之后一些使网页内容静态化的尝试。但是就像之前说的，这些尝试其实都是治标没有治本，过一段时间问题又重新出现。看着每天服务器不停的扩容，重启的alert，还有飙涨的费用，让我下定决心对strapi-cms的代码进行更进一步的阅读，尝试找到问题的原因。

经过不停的对代码的阅读和实验，我最开始有一个印象就是数据读取非常耗cpu而且慢，但是并不知道是具体哪块代码导致的。后来在github上面查了一下，发现之前就有不少人回报这方面的问题。在github的这个issue（https://github.com/strapi/strapi/issues/8552）里面就有一个高赞的回答提到strapi-cms在处理relation的时候会将所有的资料都全部抓出来，而不是使用limit让db之返回所需要的资料（原文：Generally speaking, most of the performance issues related to relation population in general (or fields) where we are requesting everything from the database, then cleaning up the data before passing it to the user. Instead Strapi needs to only request the fields required.）。换句话说，本来让db处理的filter现在变成应用处理，这样db需要返回更多的资料，同时app也需要处理这些资料并filter掉无用的部分，造成了资源的浪费。这在数据量不多的时候看不出来问题，但是数据一旦增多，整个处理时间就会变长。比较遗憾的是，这个问题直到去年底都依然没有解决，而且strapi-cms的一个成员说要解决这个问题需要重写graphql plugin和重新设计数据库。但是问题肯定是要解决的，目前cms的系统已经用了一段时间了，重新换一个系统并不现实。于是硬着头皮继续看strapi-cms的源码。js是一个很灵活的语言，strapi-cms又是一个比较大的项目，光是项目依赖就有上百个包。而且strapi-cms会用到一些全局变量，有时候看起来真是云里雾里。但是不管怎么说总是有了方向。

有了这个方向之后，我再回到code里面去看，果然发现issue里面所提到的问题，并且找到了导致问题的代码。以下就是graphql plugin中loader.js的一段代码函数，主要的作用就是去db抓取相关field的资料。比如在graphql的schema中的model会有一些复杂的field，这些field不是像string,integer这些简单的数据结构，而是连接另一个model, 这时graphql server就需要去另一个model/另一张表抓取数据。

```js
  makeQuery: async function (model, query = {}) {
    if (_.isEmpty(query.ids)) {
      return [];
    }

    // Retrieving referring model.
    const ref = this.retrieveModel(model, query.options.source);
    const ast = ref.associations.find(ast => ast.alias === query.alias);

    const params = {
      ...query.options,
      populate: ast ? [query.alias] : [], // Avoid useless population for performance reason
      query: {},
      _start: 0,  // Don't apply start or skip
      // 没有limit的限制，导致抓取全部数据
      _limit: -1,  // Don't apply a limit  
    };

    params.query[`${query.alias}_in`] = _.chain(query.ids)
      .filter(id => !_.isEmpty(id) || _.isInteger(id)) // Only keep valid ids
      .map(id => id.toString()) // convert ids to string
      .uniq() // Remove redundant ids
      .value();

    // Run query and remove duplicated ID.
    const request = await strapi.plugins['content-manager'].services[
      'contentmanager'
    ].fetchAll({ model }, params);

    return request && request.toJSON ? request.toJSON() : request;
  },
```

可以看到在以上的函数中，抓取的数据并没有限制数量，限制数量的部分是在之后另一个函数mapdata中完成的，这就产生了之前说的，可能大量无关的数据也被抓取，导致处理时间变长的情况。而且随着数据量增大，情况会变的越来越糟。所以这一块是必须要限制数量的，解决方法也很简单，将_start,:0, _limit: -1这两行注释掉后，就会根据客户端传入的参数抓取所需的资料。这里也可以根据情况限定一个最大的limit，可以保证抓取的数据量可控，避免了随着数据库中资料量变大，query变慢的情况。既然这么简单就解决了，为什么这么久都没有人去实现呢？而且这两行代码作者还专门做了注释，说明作者意识到必须全部抓取才行。仔细看了下代码，原来在抓取数据的时候，有可能会出现多个query的情况，通过异步抓取所有query之后有一个整合，如果所有返回的资料量加起来大于limit，那么最后重整的时候就会出现问题。所以只好一股脑把所有资料都先抓下来，然后在重新filter。如果只有一个query或者提前知道多个query返回的数量不会超过limit就可以对limit进行限制，做到只从db抓取所需要的数据。经过测试，我们的cms正好满足这个要求，正好可以使用这个优化方式。框架需要考虑到方方面面的情况，毕竟需要面向各种使用者。而使用者则根据自己的需求，对这个框架进行一些修改作出一些取舍来达到自己的要求。比如这个修改看起来有些hack, 但是成本低，而且确实可以解决问题。不好的方面就是可能引入bug，可能导致后续开发出现问题，尤其是不熟悉这部分代码改动的人接受项目的时候容易出问题。不过两害相权取其轻，这个修改还是值得的。而且通过添加README等文档来减少这方面的风险，或者直接已warning的形式log在console里面，这样下一个开发者就可以看到。

对cms的优化，来来回回其实已经有一年了。一开始cms对我来说就是一个黑盒子，我不知道他是怎么启动的，也不知道graphql服务器在里面是如何运作。对于导致服务器响应慢的原因也只是有一个模糊的猜测。直到后面随着对框架代码的熟悉，从添加缓存开始，一步步的优化，直到现在终于可以说是基本上完全搞清楚响应慢的原因，而且是定位到代码上的。中间走了不少弯路，尝试了不同的方法，比如将管理员输入的资料在保存时直接cache，从而使整个cms实现静态化。这条路理论上是走的通的，但是实现起来很复杂，最后也只在部分资料上实现。所以目前这个最新解决方案虽然有副作用，但是我也已经满意了。回顾整个优化过程，从发现问题，定位问题，到最后解决问题，最大的收获就是提高了定位解决问题的能力。整个过程就像是探案，一开始一头雾水，只有一些有限的，表面的线索。通过了解框架的运作方式，使用各种方法实验，最后得到更多的线索，从而缩小可能出现问题的地方。一步步直到最后定位到相关的函数代码。中间其实是一个不断循环的过程，从提出假设，验证，在根据结果进一步缩小范围，提出更加精确的假设。在这个过程中，对strapi-cms这个框架，尤其是graphql-plugin的运作方式也越来越了解。总的来说，这次探索之旅是比较愉快的，满足了好奇心的同时，也给我带来了成就感。