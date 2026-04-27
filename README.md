# StarVote

轻量级的评分投票系统，部署在vercel，使用Superbase数据库。

部署参考：<https://blog.hzchu.top/2025/StarVote%E7%9A%84python%E5%AE%9E%E7%8E%B0/>

新增功能：取消当前点赞/评分

新增功能：批量查询点赞信息（降低前端并发请求）

接口示例：

`GET /api/vote/batch_info?ids=memo-1,memo-2,memo-3`

返回结构：

`{"votes":[{"id":"memo-1","up":0,"down":0,"createdAt":null,"updatedAt":null}]}`

说明：

- 按传入 `ids` 的原顺序返回。
- 不存在的 id 也会返回默认值（`up/down=0`）。
- 单次最多查询 `200` 个 id，超过会返回 `400`。
- 现有 `/api/vote/info`、`/api/vote/update`、`/api/vote/cancel` 行为保持不变。
