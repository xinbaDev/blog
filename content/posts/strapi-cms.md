---
title: "strapi-cms中deep filtering的问题"
date: 2022-05-28T11:12:22+11:00
draft: false
summary: 最近在研究stapi-cms优化的时候看到console里面一个warning，"Deep filtering queries should be used carefully (e.g Can cause performance issues). When possible build custom routes which will in most case be more optimised." 看到这个warningw我一开始是一头雾水的，于是打算调查一下。 
---

最近在研究stapi-cms优化的时候看到console里面一个warning，"Deep filtering queries should be used carefully (e.g Can cause performance issues). When possible build custom routes which will in most case be more optimised." 看到这个warning我一开始是一头雾水的，于是打算调查一下。 

看到这个warning, 我首先产生了几个问题：
1. 什么是deep filtering?
2. 为什么deep filtering会影响performance, 具体是怎么影响？

于是先在github上搜索找到相关的issue,也并没有看到特别相关的内容，只看到一个issue#5593提到这个warning, 但是里面也没有具体讨论。然后专门查了一下deep filtering的解释，所谓的deep filtering就是filter中带有relation，在filter时需要join的那种。解释还是比较模糊，于是专门在vscode里搜索关键字Deep filtering，找到warning的定位在strapi-util.js中buildQuery函数中出现。

```js
const buildQuery = ({ model, filters = {}, ...rest }) => {
  // Validate query clauses
  if (filters.where && Array.isArray(filters.where)) {
    const deepFilters = filters.where.filter(({ field }) => field.split('.').length > 1);
    if (deepFilters.length > 0) {
      strapi.log.warn(
        'Deep filtering queries should be used carefully (e.g Can cause performance issues).\nWhen possible build custom routes which will in most case be more optimised.'
      );
    }

    // cast where clauses to match the inner types
    filters.where = filters.where
      .filter(({ value }) => value)
      .map(({ field, operator, value }) => {
        const { model: assocModel, attribute } = getAssociationFromFieldKey({
          model,
          field,
        });

        const { type } = _.get(assocModel, ['attributes', attribute], {});
        return { field, operator, value: castValueToType({ type, value }) };
      });
  }

  const orm = strapi.hook[model.orm];

  // call the orm's buildQuery implementation
  return orm.load().buildQuery({ model, filters, ...rest });
};
```

通过这段函数就可以发现，在strapi-cms中deep filter就是filters.where里面field有点号分隔的字段的情况。函数之后会处理filters.where，通过getAssociationFromFieldKey这个函数找到相关的model，最后调用orm中的buildQuery函数。看到这里依然不清楚为什么deep filtering会影响performace以至于写这段代码的dev特意写一个warning。于是继续看下去，去查看strapi-cms中的调用的orm的代码。在strapi-cms使用的是bookshelf这个orm, 具体的代码在strapi-hook-bookshelf这个package中。

```js
/**
 * Build filters on a bookshelf query
 * @param {Object} options - Options
 * @param {Object} options.model - Bookshelf model
 * @param {Object} options.filters - Filters params (start, limit, sort, where)
 */
const buildQuery = ({ model, filters }) => qb => {
  if (_.has(filters, 'where') && Array.isArray(filters.where)) {
    qb.distinct();
    buildJoinsAndFilter(qb, model, filters.where);
  }
  ...
};

const buildJoinsAndFilter = (qb, model, whereClauses) => {

  ...
  /**
   * Build a query joins and where clauses from a query tree
   * @param {Object} qb - Knex query builder
   * @param {Object} tree - Query tree
   */
  const buildQueryFromTree = (qb, queryTree) => {
    // build joins
    Object.keys(queryTree.children).forEach(key => {
      const subQueryTree = queryTree.children[key];
      buildJoin(qb, subQueryTree.assoc, queryTree, subQueryTree);

      buildQueryFromTree(qb, subQueryTree);
    });

    // build where clauses
    queryTree.where.forEach(w => buildWhereClause({ qb, ...w }));
  };

  /**
   * Add table joins
   * @param {Object} qb - Knex query builder
   * @param {Object} assoc - Models association info
   * @param {Object} originInfo - origin from which you are making a join
   * @param {Object} destinationInfo - destination with which we are making a join
   */
  const buildJoin = (qb, assoc, originInfo, destinationInfo) => {
    if (assoc.nature === 'manyToMany') {
      const joinTableAlias = generateAlias(assoc.tableCollectionName);

      qb.leftJoin(
        `${originInfo.model.databaseName}.${assoc.tableCollectionName} AS ${joinTableAlias}`,
        `${joinTableAlias}.${singular(originInfo.model.globalId.toLowerCase())}_${originInfo.model.attributes[assoc.alias].column
        }`,
        `${originInfo.alias}.${originInfo.model.primaryKey}`
      );

      qb.leftJoin(
        `${destinationInfo.model.databaseName}.${destinationInfo.model.collectionName} AS ${destinationInfo.alias}`,
        `${joinTableAlias}.${singular(destinationInfo.model.globalId.toLowerCase())}_${destinationInfo.model.primaryKey
        }`,
        `${destinationInfo.alias}.${destinationInfo.model.primaryKey}`
      );
      return;
    }

    const externalKey =
      assoc.type === 'collection'
        ? `${destinationInfo.alias}.${assoc.via}`
        : `${destinationInfo.alias}.${destinationInfo.model.primaryKey}`;

    const internalKey =
      assoc.type === 'collection'
        ? `${originInfo.alias}.${originInfo.model.primaryKey}`
        : `${originInfo.alias}.${assoc.alias}`;

    qb.leftJoin(
      `${destinationInfo.model.databaseName}.${destinationInfo.model.collectionName} AS ${destinationInfo.alias}`,
      externalKey,
      internalKey
    );
  };

  ...

  /**
   * Builds a Strapi query tree easy
   * @param {Array<Object>} whereClauses - Array of Strapi where clause
   * @param {Object} model - Strapi model
   * @param {Object} queryTree - queryTree
   */
  const buildQueryTree = (whereClauses, model, queryTree) => {
    for (let whereClause of whereClauses) {
      const { field, operator, value } = whereClause;
      // console.log("field:" + field)
      let [key, ...parts] = field.split('.');
      // console.log("key:" + key)
      // console.log(parts)

      const assoc = findAssoc(model, key);

      // if the key is an attribute add as where clause
      if (!assoc) {
        queryTree.where.push({
          field: `${queryTree.alias}.${key}`,
          operator,
          value,
        });
        continue;
      }

      const assocModel = findModelByAssoc(assoc);

      // if the last part of the path is an association
      // add the primary key of the model to the parts
      if (parts.length === 0) {
        parts = [assocModel.primaryKey];
      }

      // init sub query tree
      if (!queryTree.children[key]) {
        queryTree.children[key] = createTreeNode(assocModel, assoc);
      }

      buildQueryTree(
        [
          {
            field: parts.join('.'),
            operator,
            value,
          },
        ],
        assocModel,
        queryTree.children[key]
      );
    }

    return queryTree;
  };

  const root = buildQueryTree(whereClauses, model, {
    alias: model.collectionName,
    assoc: null,
    model,
    where: [],
    children: {},
  });

  return buildQueryFromTree(qb, root);
};

```

可以看到在这个函数的主要逻辑是先构建一个query tree，如果deep filtering越深（parts越多）树就越深，然后通过这个tree再去构建query。在构建query的过程中用到了递归，而且还有for循环里面的递归。递归的最后是buildJoin里面调用knex的query builder去构建sql query。knex是构建底层sql query的库，可以看到在buildJoin中对knew的调用用到了left join, 而且在manytomany的relation中会调用两次。left join是比较吃资源的query, 尤其是连接的表比较大的时候。目测这就是deep filtering会影响performance的主要原因。

下面用一个具体的例子来分析一下deep filtering， 以下是会触发warning的graphql query:

```js
ads (where: { tags: { name: "XXX" } } ) {
    name
    imgs {
        url
    }
    is_active
    link
    lang
    html
}
```
strapi-cms会将ads后面的where条件parse成以下的filter:

```js
{
  start: 0,
  limit: 100,
  where: [ { field: 'tags.name', operator: 'eq', value: 'XXX' } ]
}
```
这里的field在buildQuery中会被split成 key = tags, parts = name, 然后会递归调用生成子树。

而如果换一个query:

```js 
adtags (where: { name: "XXX" }) {
    ads {
        name
        imgs {
        url
        }
        is_active
        link
        lang
        html
    }
}
```

这个query也可以拿到所需要的资料，不同的是在buildQuery的时候就不会产生deep filtering的情况，一部分计算量被移到loader进行处理。其实本质上就是把原来一个复杂的query变成多个简单的query。这种有利有弊，并不是哪一种就更好，还是要看具体情况。我认为一般来说第一种都比第二种要好，因为较少的query次数，而且不需要在app端在重新整合数据。但是有时候deep filter太深太复杂，也会给db造成很大的压力。在某些情况下，比如需要连接的表特别大，而且在可以先filter这个表的情况下，第二种分开打query的方式就更好，因为可以提前filter掉一些无用的数据。这样db压力就会小很多，等于是让app来多分担一些db的计算。所以具体哪一种更好还是要看具体的query以及表的情况。

总而言之，因为数据库的设计多变，而且里面涉及各种表，情况千变万化，orm的框架很难照顾的面面具到，只能考虑一般的情况，尽可能适配，所以效能往往不是最优的。其实不只是框架，凡是复杂一些，应用场景比较多的软件都会有这种取舍。比如nginx，作为一个广泛使用的服务器就被用到了各种场景，nginx也是优化非常好的一个程序。但是依旧有许多nginx的改版以适应不同的场景，比如淘宝就专门开发过一个Tengine，以更好的服务高并发的需要。