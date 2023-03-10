---
Title: "Issue with Deep Filtering in Strapi CMS"
Date: 2022-05-28T11:12:22+11:00
Draft: false
Summary: Recently, while researching optimizations for Strapi CMS, I came across a warning in the console - "Deep filtering queries should be used carefully (e.g Can cause performance issues). When possible build custom routes which will in most case be more optimised." I was confused by this warning and decided to investigate it further.
---

Recently, while researching optimizations for Strapi CMS, I came across a warning in the console - "Deep filtering queries should be used carefully (e.g Can cause performance issues). When possible build custom routes which will in most case be more optimised." I was confused by this warning and decided to investigate it further.

Upon seeing this warning, I had several questions in mind:

1. What is deep filtering?
2. Why does deep filtering affect performance, and how exactly does it impact it?

I then searched on GitHub for relevant issues but did not find anything particularly related. The only issue (#5593) that mentioned this warning did not have any specific discussion about it. I then looked up the definition of deep filtering, which refers to filtering that involves relations and requires joining when filtering. However, the explanation was still somewhat unclear. I then searched for the keyword "deep filtering" in VSCode and found that the warning was located in the buildQuery function in strapi-util.js.

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

Through this function, we can discover that deep filtering in Strapi CMS refers to the situation where the field in the filters.where clause is a field separated by a dot. After processing the filters.where clause, the function uses the getAssociationFromFieldKey function to find the relevant model, and finally calls the buildQuery function in the ORM. If you're still unclear about why deep filtering affects performance to the point where the developer who wrote this code felt it necessary to include a warning, you can continue reading and look at the ORM code used in Strapi CMS. Strapi CMS uses the bookshelf ORM, and the specific code can be found in the strapi-hook-bookshelf package.

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

You can see that the main logic of this function is to first construct a query tree. The deeper the deep filtering (the more parts), the deeper the tree. Then, this tree is used to construct the query. Recursion is used in the query construction process, and there is also recursion inside the for loop. The end result of the recursion is the buildJoin function, which calls Knex's query builder to construct the SQL query. Knex is a library that builds low-level SQL queries. In the buildJoin function, a left join is used in the call to Knex, and it is called twice in the many-to-many relation. Left join is a resource-intensive query, especially when connecting to large tables. It appears that deep filtering is the main reason for performance degradation.

Below is an example of a GraphQL query that triggers a warning.

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
The strapi-cms will parse the where condition after "ads" into the following filter:


```js
{
  start: 0,
  limit: 100,
  where: [ { field: 'tags.name', operator: 'eq', value: 'XXX' } ]
}
```
In this filter, the "field" will be split into "key" as "tags" and "parts" as "name" in the buildQuery function. It will then recursively generate a subtree.

If a different query is used:

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

This query can also retrieve the required information, but the difference is that there won't be deep filtering during buildQuery, and part of the computation will be handled by the loader. Essentially, a complex query is broken down into multiple simple queries. This approach has its advantages and disadvantages, and there is no one-size-fits-all solution - it depends on the specific situation. Generally, I believe the first approach is better because it involves fewer queries, and there is no need to re-integrate data on the app side. However, in some cases, when the deep filter is too complex and puts too much pressure on the database, the second approach of splitting the query may be better, especially when dealing with large tables that can be filtered in advance to eliminate unnecessary data. This reduces the database workload, effectively allowing the app to share some of the computation burden. Therefore, which approach is better depends on the specific query and table conditions.

In summary, because database design is so variable and involves many tables, ORM frameworks can't cater to every possible scenario and can only consider general cases as much as possible, which means that performance is often not optimal. This is not just true for frameworks; any software that is somewhat complex and has many use cases will face similar trade-offs. For example, Nginx is a widely used server that has been deployed in various scenarios. Despite being a very well-optimized program, there are still many modified versions of Nginx, such as Tengine, which has been specifically developed to better serve high-concurrency needs.