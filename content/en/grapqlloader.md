---
Title: "Exploring optimization of GraphQL plugin in Strapi CMS"
Date: 2022-05-13T11:18:22+11:00
Draft: false
Summary: Recently, the CMS server has been showing red lights again. Although various optimizations have been made over the past year, such as adding caching and reducing database access, they only provide temporary relief. As the amount of data continues to increase, the problem reemerges. For example, after the cache expires, the server becomes overloaded for a period of time, resulting in slow response times or even crashes. To address this problem, the CMS was migrated to Kubernetes with multi-node deployment to improve availability. This certainly improves the user experience, but the problem has not been truly solved. The server still slows down every day and even restarts due to increased costs from autoscaling. I could reduce this problem by increasing the server configuration, but that would be going back to the old approach. It's necessary to optimize the code level.

---

Recently, the CMS server has been showing red lights again. Although various optimizations have been made over the past year, such as adding caching and reducing database access, they only provide temporary relief. As the amount of data continues to increase, the problem reemerges. For example, after the cache expires, the server becomes overloaded for a period of time, resulting in slow response times or even crashes. To address this problem, the CMS was migrated to Kubernetes with multi-node deployment to improve availability. This certainly improves the user experience, but the problem has not been truly solved. The server still slows down every day and even restarts due to increased costs from autoscaling. I could reduce this problem by increasing the server configuration, but that would be going back to the old approach. It's necessary to optimize the code level.

The current CMS is using the Strapi-CMS framework, version v3-beta, which includes a plugin that uses GraphQL. Prior to this, I had explored code optimization. First, I read through the app's code and discussed it with my colleagues who were writing the code. We concluded that the application was slowing down due to the framework. So I began reading the framework's code, particularly the GraphQL plugin. This led to me adding a cache to GraphQL. I also made some attempts at static website content, but as I mentioned before, these were only temporary fixes and the problem reoccurred after a period of time. Watching the server constantly expand and restart, alerts going off, and costs skyrocketing, I made the decision to further read the code of Strapi-CMS and try to find the root of the problem.

My initial impression was that data reading was very CPU-intensive and slow, but I didn't know exactly which part of the code was causing the issue. Later, I checked on GitHub and found that many people had reported similar problems before. In this issue on GitHub (https://github.com/strapi/strapi/issues/8552), a highly upvoted response mentioned that when Strapi CMS processes relations, it retrieves all the data instead of using a limit to return only the necessary data from the database. In other words, the filter that was originally handled by the database is now handled by the application, which requires the database to return more data, and the application also needs to filter out the unnecessary parts, resulting in wasted resources. This problem may not be apparent when dealing with small amounts of data, but as the data grows, the processing time will become longer. Unfortunately, this problem has not been resolved until the end of last year, and a member of the Strapi CMS team said that solving this problem requires rewriting the GraphQL plugin and redesigning the database. However, the problem must be solved, and the CMS system has been used for some time, so it is not practical to switch to a new system. So I continued to study the source code of Strapi CMS with perseverance. JavaScript is a very flexible language, and Strapi CMS is a relatively large project with hundreds of dependencies. Moreover, Strapi CMS uses some global variables, which sometimes make it difficult to understand. But in any case, I have found a direction.

After finding this direction, I went back to the code and, after reading and experimenting with the code repeatedly, I indeed discovered the problems mentioned in the issue and found the code that caused the issue. The following is a code function in the loader.js file of the GraphQL plugin, which is mainly used to fetch information related to fields from the database. For example, in the GraphQL schema, there may be some complex fields in the model, which are not simple data structures like strings and integers, but are connected to another model. In this case, the GraphQL server needs to fetch data from another model/another table.

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
      // The lack of limit restrictions resulted in fetching all the data.
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

In the above functions, we can see that there is no limit on the number of data being fetched. The limitation on the quantity is accomplished in another function called "mapdata." This can lead to a situation where a large amount of irrelevant data is also being fetched, causing an increase in processing time. As the data volume increases, the situation can become even worse. Therefore, it is necessary to limit the quantity in this area. The solution is simple: comment out the lines "_start:0" and "_limit: -1," and the required data will be fetched based on the parameters passed in by the client. Here, a maximum limit can also be specified to ensure that the amount of data fetched is controllable, avoiding the situation where the query becomes slow as the amount of data in the database increases.

Since the solution is so simple, why hasn't anyone implemented it before? The author even left comments on these two lines of code, indicating that all the data must be fetched. Upon closer inspection of the code, it turns out that multiple queries may occur when fetching data, and after asynchronously fetching all the queries, they are integrated. If the total amount of data returned exceeds the limit, problems may arise when reorganizing at the end. Therefore, it is necessary to fetch all the data first, and then filter it again. If there is only one query, or if it is known in advance that the number of returns from multiple queries will not exceed the limit, the limit can be restricted to only fetch the required data from the database. After testing, our CMS just meets this requirement, and this optimization can be implemented.

The framework needs to consider all aspects of the situation, after all, it needs to be oriented towards various user cases. Users can modify the framework according to their own needs, making some choices and trade-offs to meet their own needs. For example, this modification may seem a bit hacky, but the cost is low, and it can indeed solve the problem. The downside is that it may introduce bugs and may cause problems in later development, especially for those who are not familiar with this part of the code. However, the benefits outweigh the drawbacks, and this modification is worthwhile. Moreover, by adding documentation such as a README or logging in console with warnings, the risk can be mitigated.

Over the course of a year, optimizing the CMS has been a back-and-forth process. Initially, the CMS was a mystery to me - I had no idea how it started or how the GraphQL server worked within it. I only had a vague idea as to why the server response was slow. It wasn't until later, as I became more familiar with the framework, starting with adding caching and step-by-step optimization, that I was finally able to identify the root cause of the slow response - a problem located within the code. Throughout this journey, I tried various methods, such as caching administrator-entered data upon saving to achieve a static CMS. Although theoretically effective, implementing this approach was complex and only applied to some data in the end. Nevertheless, despite the side effects of my latest solution, I'm satisfied with the result. Reflecting on the entire optimization process, the biggest takeaway is my improved problem-solving ability. This process was akin to solving a mystery, starting with limited and surface-level clues. By experimenting with different methods, gaining a better understanding of the framework, and narrowing down potential problem areas step-by-step, I was able to pinpoint the relevant function code. This process involved a continuous loop of proposing hypotheses, verifying them, and further refining them based on the results. Through this experience, I've gained a better understanding of the Strapi CMS framework, particularly the operation of the GraphQL plugin. Overall, this exploration journey has been both enjoyable and fulfilling, as it satisfied my curiosity and gave me a sense of achievement.