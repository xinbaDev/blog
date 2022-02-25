---
title: "记一次对sql的调试和优化(Postgres query planner)"
date: 2021-06-13T19:33:00+11:00
summary: 最近在工作中碰到一个很有趣的sql问题。几乎同样的raw sql，最后执行出来的时间居然相差百倍不止。通过对这个问题的调试研究，对sql的执行过程（postgres）以及相应的优化有了更深的认识。
draft: false
---

最近在工作中碰到一个很有趣的sql问题。几乎同样的raw sql，最后执行出来的时间居然相差百倍不止。通过对这个问题的调试研究，对sql的执行过程（postgres）以及相应的优化有了更深的认识。

出现问题的raw sql(经过简化，提高易读性):
```
# 返回是从早上10点（开盘）到下午4点（收盘）的所有热门股票的价格数据
SELECT "marketdata"."id", 
       "marketdata"."code_id", 
       "marketdata"."date",  
       "marketdata"."price",  
FROM "marketdata" INNER JOIN "stock" ON 
("marketdata"."code_id" = "stock"."code") 
WHERE (
    "stock"."is_hot" = true AND 
    "marketdata"."date" BETWEEN '2019-06-25T10:00:00' AND '2019-06-25T16:00:00') 
ORDER BY "marketdata"."date" ASC
```

## 0x01 事情的起因

我们公司主要做的是澳股资讯研究分析，包括发布澳交所ASX全部澳股的价格、走势、公告和其它重要市场资讯。最近因为项目要求，给股票增加了一个新的叫special的分类。
之前已经有许多的分类，比如热门股，中概股，金矿股等。所以这一块添加一个新分类并不是什么大需求。只要在db中的stock table里面新增一个分类（通过在stock的scheme里添加一个is_special的column），再在相应api里加入is_special的filter就大功告成。没想到就是这么简单的需求却让我学到了很多东西：）

首先新功能在staging一上线，就发现相应的api响应时间比其他同类型的api要长。正常的api最多1秒也返回了，这个新增的api却需要惊人的30-40秒，甚至timeout。但是在本地测试的时候并没有这个问题。马上git diff一下之前的改动，一方面确认没有低级的代码逻辑错误，一方面也是带着问题看code往往有帮助发现问题的原因。很快就排除了代码的原因导致超长响应（因为基本没有什么改动），不过在快速看代码的过程中发现，每当cache失效的时候，api会去db读取相应数据并写入缓存。结合之前测试的表现，马上怀疑是db端出了问题。于是看了下aws monitor, 发现上线后db读取次数激增， 确认是db端出了问题。我的第一个猜测是漏加index了，但是通过检查很快就排除。之后通过一些debug工具，得到相应ORM产生的raw sql（如上）。经测试，is_hot正常，is_special就非常慢。至此，故障的原因已经通过排除缩小到一个比较小的范围，可以导致出错的变量已经大大缩小了。剩下来的问题就是

    看上去只是is_hot换成is_special而已，为什么is_special就这么慢呢？ 
    
    
## 0x02 DB Query慢的初步分析

首先看看这两个query有什么不同。从表面上看，只是is_hot变成了is_special。但是在底下，db会把所有is_special/is_hot = True的stock读取出来。is_special是新加入的类别，只有两个股票，读取所有数据也才360(一天的价格数据条数) * 2 =720条。而is_hot则是代表热门股，有上百个股票，360 × 100 = 360000条 。基本相同的sql query, 为什么query数据量大的反而比数据量小的执行速度快？

这里面就涉及了postgres是如何执行这条sql语句的。之前了解过，数据库对query的处理最主要的一步是planning。以postgres为例，当db收到sql query的时候，db会根据之前的一些[统计数据]()，通过对query所有可能的组合形式（如何scan, 如何join, 如何order）进行耗时估计，尽快的找出耗时最少的执行方案，然后再执行。如何查看db如何估计并找出最优解呢？postgres里面有一个命令， [EXPLAIN ANALYZE]().

接下来，我们看看这两条“兄弟”query在db这边是如何执行的。

首先是is_hot
```
Sort  (cost=119007.54..119066.60 rows=23621 width=241) (actual time=116.795..127.942 rows=37125 loops=1)"
  Sort Key: marketdata.date"
  Sort Method: external merge  Disk: 4800kB"
  ->  Nested Loop  (cost=24.31..114544.24 rows=23621 width=241) (actual time=0.185..73.446 rows=37125 loops=1)"
        ->  Seq Scan on stock  (cost=0.00..441.12 rows=100 width=4) (actual time=0.066..1.211 rows=100 loops=1)"
              Filter: is_hot"
              Rows Removed by Filter: 2492"
        ->  Bitmap Heap Scan on marketdata  (cost=24.31..1138.09 rows=294 width=241) (actual time=0.107..0.503 rows=371 loops=100)"
              Recheck Cond: (((code_id)::text = (stock.code)::text) AND (date >= '2019-06-25 00:00:00.331101+00'::timestamp with time zone) AND (date <= '2019-06-25 08:08:55.331109+00'::timestamp with time zone))"
              Heap Blocks: exact=37119"
              ->  Bitmap Index Scan on marketdata_code_id_date_e4afd606_idx  (cost=0.00..24.23 rows=294 width=0) (actual time=0.068..0.068 rows=371 loops=100)"
                    Index Cond: (((code_id)::text = (stock.code)::text) AND (date >= '2019-06-25 00:00:00.331101+00'::timestamp with time zone) AND (date <= '2019-06-25 08:08:55.331109+00'::timestamp with time zone))"
Planning time: 0.704 ms"
Execution time: 135.848 ms"

```

图形化显示(由[pev](https://tatiyants.com/pev)产生）:

![](https://i.imgur.com/okyfgCI.png)



接着是is_special

```
Sort  (cost=725081.36..725852.57 rows=308485 width=241) (actual time=44276.683..44276.954 rows=1125 loops=1)"
  Sort Key: marketdata.date"
  Sort Method: quicksort  Memory: 250kB"
  ->  Hash Join  (cost=457.44..625254.48 rows=308485 width=241) (actual time=37102.527..44274.947 rows=1125 loops=1)"
        Hash Cond: ((marketdata.code_id)::text = (stock.code)::text)"
        ->  Seq Scan on marketdata  (cost=0.00..619398.55 rows=616970 width=241) (actual time=36321.218..44015.861 rows=783850 loops=1)"
              Filter: ((date >= '2019-06-25 00:00:00.331101+00'::timestamp with time zone) AND (date <= '2019-06-25 08:08:55.331109+00'::timestamp with time zone))"
              Rows Removed by Filter: 18213401"
        ->  Hash  (cost=441.12..441.12 rows=1306 width=4) (actual time=4.070..4.070 rows=3 loops=1)"
              Buckets: 2048  Batches: 1  Memory Usage: 17kB"
              ->  Seq Scan on stock  (cost=0.00..441.12 rows=1306 width=4) (actual time=4.059..4.064 rows=3 loops=1)"
                    Filter: is_special"
                    Rows Removed by Filter: 2589"
Planning time: 0.692 ms"
Execution time: 44277.220 ms"
```

图形化显示：

![](https://i.imgur.com/n9FBnAJ.png)

关于如何读EXPLAIN ANALYZE,请参考[Reading a Postgres EXPLAIN ANALYZE Query Plan](https://thoughtbot.com/blog/reading-an-explain-analyze-query-plan), 或者[PostgreSQL执行计划的解释](https://blog.csdn.net/ls3648098/article/details/7602136)。这里不再敖述。

可以看到，两个几乎一样的query在db执行的过程中却大不相同。is_hot，is_special在最后都进行了sorting。is_hot因为数据量大，已经超过memory限制，最后用的是external merge，在硬盘中实现。而is_special数据量小，可以完全在内存中使用quick sort算法。 因为硬盘的操作比内存的操作要慢的多（上百倍），按照常理来说，is_special应该要比is_hot要快才对，但是最后结果却相反，说明在最后sorting之前is_special有非常耗时的操作。我们继续往下看，很快就会发现在is_special中有一个特别耗时的操作。Seq Scan on marketdata  (cost=0.00..619398.55 rows=616970 width=241) (actual time=36321.218..44015.861 rows=783850 loops=1)" 。这个操作会遍历读取整个table的数据，这个table根据postgres估计有616970行（实际上有783850行），对这么大的一个table进行顺序遍历，注定非常耗时的。最后整个query的时间都被这个操作大大拖长。反观，在is_hot的情况下，对这个大table所采用的scan方式是先bitmap index scan,再bitmap heap scan，quey的时间相比第一种大大减少。分析到这里，问题的源头已经近一步缩小。基本可以确定是postgres query planner出了问题，并没有找到最优的解。接下来的问题是，为什么postgres的query planner会作出这样的决定，其依据是什么？

## 0x03 进一步分析sql query planner

首先可以看到在is_special的query中，postgres对is_special=True在表中数量估计产生了严重的偏差（估计1306行，可实际才3行）。而is_hot中，postgres作出了正确的估计（估计100行,实际也是100行）。

这个错误估计直接导致bitmap heap scan和Nested Loop的估计时间比实际值高出许多倍。bitmap heap scan从循环3次，错误估计要循环1306次。Nested Loop从实际的3 × 360 × 3次变成1306 × 360 × 1306次。 导致最后query planner也只能选择另一种虽然非常耗时，但是比错误估计时间要少的方案。为什么postgres对is_speical=True的行数估计出现如此大的偏差？ 这就涉及到postgres是如何估计qeury所涉及的行数。经过查找官方的[Row Estimation文档](https://www.postgresql.org/docs/10/row-estimation-examples.html), 发现在pg中有一个MCV(most common values)概念，官方文档已经将的很清楚，这里因为时间问题不再敖述。总之，postgres将在一个叫pg_stats的view中column的关于MCV的统计数据，并通过统计数据来估计相关query所涉及的行数。按照官方文档的例子，照猫画虎，查找stock表中column是is_special统计数据。

```
SELECT null_frac, n_distinct, most_common_vals, most_common_freqs
       FROM pg_stats
       WHERE tablename='stock' and attname='is_special';
  
```
返回结果

```
 null_frac | n_distinct | most_common_vals | most_common_freqs 
-----------+------------+------------------+-------------------
(0 rows)

```
预期看到错误的统计数并没有看到，返回的是空值，说明数据库并没有相关的统计数据。这里产生了两个问题，

（1） 统计数据是由谁产生的？为什么没有？
（2） 没有统计数据，之前Postgres是怎么估计出有is_special=True的行数的？

先说第一个，根据[官方文档](https://www.postgresql.org/docs/10/routine-vacuuming.html)统计数据是由一个Autovacuum Daemon产生的。这个Daemon非常重要，除了生成统计数据之外，还负责
1. To recover or reuse disk space occupied by updated or deleted rows.
2. To update the visibility map, which speeds up index-only scans.
3. To protect against loss of very old data due to transaction ID wraparound or multixact ID wraparound.

因为和主题不相关，这里也不做具体展开，反正很重要就对了。 在同一份文档中讲到
> For analyze, a similar condition is used: the threshold, defined as:
> 
> > analyze threshold = analyze base threshold + analyze scale factor * number of tuples
> > 
紧接着：
> The default thresholds and scale factors are taken from postgresql.conf...
> 
赶紧打开一看:

> #autovacuum_analyze_threshold = 50      # min number of row updates before analyze
> #autovacuum_analyze_scale_factor = 0.1  # fraction of table size before analyze

怪不得没有相关数据，因为远远没有达到threshold。

至于第二个问题,官方文档并没有具体说明，在统计数据不可用的情况下，行数到底是如何估计的。

这块要在postgres的source code里面找。我是从optimizer/path里面的cost_seqscan函数开始找。思路是通过cost的函数找到调用统计数据的函数。一路跟到在selfuncs.c中的booltestsel函数:

```
/*
 * booltestsel		- Selectivity of BooleanTest Node.
 */
 
Selectivity
booltestsel(PlannerInfo *root, BoolTestType booltesttype, Node *arg,
			int varRelid, JoinType jointype, SpecialJoinInfo *sjinfo)
{

    ...

	else
	{
		/*
		 * If we can't get variable statistics for the argument, perhaps
		 * clause_selectivity can do something with it.  We ignore the
		 * possibility of a NULL value when using clause_selectivity, and just
		 * assume the value is either TRUE or FALSE.
		 */
		switch (booltesttype)
		{
			case IS_UNKNOWN:
				selec = DEFAULT_UNK_SEL;
				break;
			case IS_NOT_UNKNOWN:
				selec = DEFAULT_NOT_UNK_SEL;
				break;
			case IS_TRUE:
			case IS_NOT_FALSE:
				selec = (double) clause_selectivity(root, arg, varRelid, jointype, sjinfo);
				break;
			case IS_FALSE:
			case IS_NOT_TRUE:
				selec = 1.0 - (double) clause_selectivity(root, arg, varRelid, jointype, sjinfo);
				break;
			default:
				elog(ERROR, "unrecognized booltesttype: %d",
					 (int) booltesttype);
				selec = 0.0;	/* Keep compiler quiet */
				break;
		}
	}


```
根据注释，对于boolean类型的值，如果db找不到统计信息，会排除null的情况，按照不是True就是False情况来做估计。按照stock的表中一共有2598行，那么估计出来的is_special=True的行数应该在1300行左右。这也与EXPLAIN ANALYZE时的情况相符。


## 0x04 解决方法

根据文档，手动analyze相关的table的column,强制更新pg_stats中的数据，使query planner能根据准确数据来作出planning。或者针对stock这个table调整threshold的值，让autovacuum daemon去干活，也能解决这个问题。

还有一种做法是直接告诉query planner所涉及到的codes, 让query planner不要瞎猜，这样也能得到最优解。我个人倾向使用这种方法。这也是在有充足时间进一步分析sql query planner之前，hot fix的时候使用的方法。因为直觉已经告诉我sql在估计时间的时候出了问题。我认为比起最终找到问题原因而得到的方法相比， hot fix时使用的方法更好。优点是首先易于迁移，以后迁移到其他数据库的时候不需要在去调整新的postgres。还有就是减少query planner的loading，让query planner能更稳的找到最佳执行路径。

## 0x05 反思

通过这次debug，我查找了大量资料和测试，对postgres的运行和优化有了更深的认识。有一个感悟就是postgres的query planner真不容易，作为程序员在设计query的时候应该多为query planner着想。尽量不要让query planner瞎猜，query不要太复杂，该加index还是要加。

在调查的过程中碰到了很多有意思的资料，尤其关于db优化方面。其实不止postgres这种关系型数据库，非关系型数据库像Mongodb也有[sql planning问题以及对应的优化](https://docs.mongodb.com/manual/core/query-plans/)。中间其实还查阅很多资料，但是和主题不是强相关都没有放上来，比如说优化方面，以后有机会会专门写一篇关于数据库的优化心得。

学习到了深处，确实有一种殊途同归的感觉。总而言之，通过这次debug, 从查找资料，到源码的追踪，最大的收获是postgres对我来说再也不是黑箱子了，同时对数据库的优化有了更深的理解。


## Reference

1. https://thoughtbot.com/blog/advanced-postgres-performance-tips
2. https://www.postgresql.org/docs/9.3/row-estimation-examples.html
3. https://gocardless.com/blog/debugging-the-postgres-query-planner
4. https://blog.dbi-services.com/are-statistics-immediately-available-after-creating-a-table-or-an-index-in-postgresql/
5. https://www.postgresql.org/docs/10/routine-vacuuming.html
6. https://docs.mongodb.com/manual/tutorial/analyze-query-plan/
7. https://thoughtbot.com/blog/reading-an-explain-analyze-query-plan
8. https://www.smartly.io/blog/letting-postgresql-plan-well-for-you-markus-winand
9. https://blog.csdn.net/kmblack1/article/details/80761647
10. https://www.cnblogs.com/kissdodog/p/3160560.html
11. https://docs.mongodb.com/manual/core/query-plans/