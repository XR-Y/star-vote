# -*- coding:utf-8 -*-
import json
from fastapi import FastAPI,Response, Request
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import psycopg2
import math
from html import escape
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
app = FastAPI(docs_url=None, redoc_url=None)

allowedHosts = os.getenv("ALLOWED_HOSTS")
databaseUrl = os.getenv("DATABASE_URL") 
amdinPWD = os.getenv("ADMIN_PWD")
MAX_BATCH_VOTE_IDS = 200
VIEW_PWD = os.getenv("VIEW_PWD", "xryu")
MAX_VIEW_LOG_ROWS = 100

VIEW_PERIODS = {
    "24h": ("最近 24 小时", timedelta(hours=24)),
    "7d": ("最近 7 天", timedelta(days=7)),
    "30d": ("最近 30 天", timedelta(days=30)),
    "all": ("全部时间", None),
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=str(True),
    allow_methods=["*"],
    allow_headers=["*"],
)


def getClientIp(request: Request):
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()

    x_real_ip = request.headers.get("x-real-ip", "")
    if x_real_ip:
        return x_real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def getClientLocation(request: Request):
    country = request.headers.get("x-vercel-ip-country") or request.headers.get("cf-ipcountry") or "Unknown"
    region = request.headers.get("x-vercel-ip-country-region") or "Unknown"
    city = request.headers.get("x-vercel-ip-city") or "Unknown"
    return country, region, city


def logOperation(request: Request, action: str, item_id: str, value: str, status: str, message: str = ""):
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS operation_log (
                id SERIAL PRIMARY KEY,
                action VARCHAR(64) NOT NULL,
                item_id VARCHAR(255) NOT NULL,
                value VARCHAR(64) NOT NULL,
                status VARCHAR(32) NOT NULL,
                message TEXT,
                ip VARCHAR(128) NOT NULL,
                ip_country VARCHAR(128) NOT NULL DEFAULT 'Unknown',
                ip_region VARCHAR(128) NOT NULL DEFAULT 'Unknown',
                ip_city VARCHAR(128) NOT NULL DEFAULT 'Unknown',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        ip = getClientIp(request)
        country, region, city = getClientLocation(request)
        cursor.execute(
            """
            INSERT INTO operation_log (
                action, item_id, value, status, message, ip, ip_country, ip_region, ip_city
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (action, item_id, value, status, message, ip, country, region, city),
        )
        connection.commit()
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Failed to log operation: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def renderViewLogin(message: str = ""):
    msg = f"<p class='msg'>{escape(message)}</p>" if message else ""
    return f"""
<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>StarVote 看板登录</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: linear-gradient(135deg, #f5f7fb, #eef2f9); min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
    .card {{ width: min(92vw, 380px); background: #fff; border-radius: 14px; padding: 28px; box-shadow: 0 10px 30px rgba(20,30,55,0.12); }}
    h1 {{ margin: 0 0 8px; font-size: 22px; color: #16233b; }}
    p {{ margin: 0 0 18px; color: #5b6780; font-size: 14px; }}
    .msg {{ color: #c62828; margin-bottom: 10px; }}
    input {{ width: 100%; box-sizing: border-box; border: 1px solid #d6deea; border-radius: 10px; padding: 12px; font-size: 14px; margin-bottom: 12px; }}
    button {{ width: 100%; border: 0; border-radius: 10px; padding: 12px; background: #1f4cff; color: #fff; font-size: 14px; cursor: pointer; }}
  </style>
</head>
<body>
  <form class='card' method='get' action='/view'>
    <h1>StarVote 看板</h1>
    <p>请输入访问密码</p>
    {msg}
    <input type='password' name='pwd' placeholder='Password' required />
    <button type='submit'>进入看板</button>
  </form>
</body>
</html>
"""


def renderDashboardHtml(stats, top_votes, logs, region_top, period_key, period_label, pwd):
    cards = [
        ("Vote 项目数", str(stats["vote_items"])),
        ("总点赞", str(stats["total_up"])),
        ("总点踩", str(stats["total_down"])),
        ("Rating 项目数", str(stats["rating_items"])),
        ("评分总次数", str(stats["rating_total"])),
        ("最近日志", str(stats["log_count"])),
    ]

    cards_html = "".join(
        f"<div class='metric'><div class='k'>{escape(k)}</div><div class='v'>{escape(v)}</div></div>"
        for k, v in cards
    )

    top_rows = "".join(
        "<tr>"
        f"<td>{escape(row['id'])}</td>"
        f"<td>{row['up']}</td>"
        f"<td>{row['down']}</td>"
        f"<td>{escape(row['updated_at'])}</td>"
        "</tr>"
        for row in top_votes
    ) or "<tr><td colspan='4'>暂无数据</td></tr>"

    log_rows = "".join(
        "<tr>"
        f"<td>{escape(row['created_at'])}</td>"
        f"<td>{escape(row['action'])}</td>"
        f"<td>{escape(row['item_id'])}</td>"
        f"<td>{escape(row['value'])}</td>"
        f"<td>{escape(row['status'])}</td>"
        f"<td>{escape(row['ip'])}</td>"
        f"<td>{escape(row['location'])}</td>"
        "</tr>"
        for row in logs
    ) or "<tr><td colspan='7'>暂无日志</td></tr>"

    region_rows = "".join(
        "<tr>"
        f"<td>{escape(row['country'])}</td>"
        f"<td>{escape(row['region'])}</td>"
        f"<td>{escape(row['city'])}</td>"
        f"<td>{row['count']}</td>"
        "</tr>"
        for row in region_top
    ) or "<tr><td colspan='4'>暂无数据</td></tr>"

    period_links = "".join(
        f"<a class='pill {'active' if key == period_key else ''}' href='/view?pwd={escape(pwd)}&period={key}'>{escape(VIEW_PERIODS[key][0])}</a>"
        for key in ["24h", "7d", "30d", "all"]
    )

    return f"""
<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>StarVote 看板</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f4f7fb; color: #19253d; }}
    .wrap {{ max-width: 1160px; margin: 24px auto; padding: 0 16px 24px; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }}
    h1 {{ margin: 0; font-size: 24px; }}
    .sub {{ color: #5d6b85; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 12px; margin-bottom: 14px; }}
    .metric {{ background: #fff; border: 1px solid #e1e8f2; border-radius: 12px; padding: 14px; box-shadow: 0 2px 6px rgba(25,37,61,0.05); }}
    .metric .k {{ color: #5f6c85; font-size: 12px; margin-bottom: 7px; }}
    .metric .v {{ font-size: 24px; font-weight: 700; }}
    .panel {{ background: #fff; border: 1px solid #e1e8f2; border-radius: 12px; padding: 14px; box-shadow: 0 2px 6px rgba(25,37,61,0.05); margin-top: 12px; }}
    .title {{ margin: 0 0 10px; font-size: 15px; }}
    .toolbar {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 14px; }}
    .pill {{ text-decoration: none; color: #31508f; background: #edf3ff; border: 1px solid #d7e4ff; padding: 6px 10px; border-radius: 999px; font-size: 12px; }}
    .pill.active {{ color: #fff; background: #1f4cff; border-color: #1f4cff; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #edf1f7; padding: 8px 6px; text-align: left; vertical-align: top; }}
    th {{ color: #5f6c85; font-weight: 600; }}
    @media (max-width: 1024px) {{ .grid {{ grid-template-columns: repeat(3, minmax(120px, 1fr)); }} }}
    @media (max-width: 640px) {{ .grid {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }} .header {{ flex-direction: column; align-items: flex-start; gap: 8px; }} }}
  </style>
</head>
<body>
  <div class='wrap'>
    <div class='header'>
      <h1>StarVote 商业看板</h1>
            <div class='sub'>Route: /view | 只读统计视图 | 时间范围：{escape(period_label)}</div>
    </div>
        <div class='toolbar'>{period_links}</div>
    <div class='grid'>{cards_html}</div>

    <div class='panel'>
      <h2 class='title'>Top 点赞内容</h2>
      <table>
        <thead><tr><th>ID</th><th>Up</th><th>Down</th><th>Updated At</th></tr></thead>
        <tbody>{top_rows}</tbody>
      </table>
    </div>

    <div class='panel'>
      <h2 class='title'>最近操作日志（含 IP 属地）</h2>
      <table>
        <thead><tr><th>Time</th><th>Action</th><th>ID</th><th>Value</th><th>Status</th><th>IP</th><th>属地</th></tr></thead>
        <tbody>{log_rows}</tbody>
      </table>
    </div>

        <div class='panel'>
            <h2 class='title'>属地来源 Top</h2>
            <table>
                <thead><tr><th>Country</th><th>Region</th><th>City</th><th>Count</th></tr></thead>
                <tbody>{region_rows}</tbody>
            </table>
        </div>
  </div>
</body>
</html>
"""


def getDashboardData(period_key: str):
    selected = period_key if period_key in VIEW_PERIODS else "7d"
    period_label, delta = VIEW_PERIODS[selected]
    since = None
    if delta is not None:
        since = datetime.now(timezone.utc) - delta

    stats = {
        "vote_items": 0,
        "total_up": 0,
        "total_down": 0,
        "rating_items": 0,
        "rating_total": 0,
        "log_count": 0,
    }
    top_votes = []
    logs = []
    region_top = []

    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS operation_log (
                id SERIAL PRIMARY KEY,
                action VARCHAR(64) NOT NULL,
                item_id VARCHAR(255) NOT NULL,
                value VARCHAR(64) NOT NULL,
                status VARCHAR(32) NOT NULL,
                message TEXT,
                ip VARCHAR(128) NOT NULL,
                ip_country VARCHAR(128) NOT NULL DEFAULT 'Unknown',
                ip_region VARCHAR(128) NOT NULL DEFAULT 'Unknown',
                ip_city VARCHAR(128) NOT NULL DEFAULT 'Unknown',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        cursor.execute(
            "SELECT COUNT(*) FROM vote WHERE (%s IS NULL OR updated_at >= %s)",
            (since, since),
        )
        stats["vote_items"] = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT COALESCE(SUM(up),0), COALESCE(SUM(down),0) FROM vote WHERE (%s IS NULL OR updated_at >= %s)",
            (since, since),
        )
        up_sum, down_sum = cursor.fetchone()
        stats["total_up"] = up_sum or 0
        stats["total_down"] = down_sum or 0

        cursor.execute(
            "SELECT COUNT(*) FROM rating WHERE (%s IS NULL OR updated_at >= %s)",
            (since, since),
        )
        stats["rating_items"] = cursor.fetchone()[0] or 0

        cursor.execute(
            'SELECT COALESCE(SUM("1" + "2" + "3" + "4" + "5"),0) FROM rating WHERE (%s IS NULL OR updated_at >= %s)',
            (since, since),
        )
        stats["rating_total"] = cursor.fetchone()[0] or 0

        cursor.execute(
            """
            SELECT id, up, down, updated_at
            FROM vote
            WHERE (%s IS NULL OR updated_at >= %s)
            ORDER BY up DESC, updated_at DESC
            LIMIT 20
            """,
            (since, since),
        )
        for row in cursor.fetchall():
            top_votes.append(
                {
                    "id": row[0],
                    "up": row[1],
                    "down": row[2],
                    "updated_at": row[3].isoformat().replace('+00:00', 'Z') if row[3] else "-",
                }
            )

        cursor.execute(
            "SELECT COUNT(*) FROM operation_log WHERE (%s IS NULL OR created_at >= %s)",
            (since, since),
        )
        stats["log_count"] = cursor.fetchone()[0] or 0

        cursor.execute(
            """
            SELECT action, item_id, value, status, ip, ip_country, ip_region, ip_city, created_at
            FROM operation_log
            WHERE (%s IS NULL OR created_at >= %s)
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (since, since, MAX_VIEW_LOG_ROWS),
        )
        for row in cursor.fetchall():
            location = " / ".join([row[5], row[6], row[7]])
            logs.append(
                {
                    "action": row[0],
                    "item_id": row[1],
                    "value": row[2],
                    "status": row[3],
                    "ip": row[4],
                    "location": location,
                    "created_at": row[8].isoformat().replace('+00:00', 'Z') if row[8] else "-",
                }
            )

        cursor.execute(
            """
            SELECT ip_country, ip_region, ip_city, COUNT(*) as cnt
            FROM operation_log
            WHERE (%s IS NULL OR created_at >= %s)
            GROUP BY ip_country, ip_region, ip_city
            ORDER BY cnt DESC, ip_country ASC, ip_region ASC, ip_city ASC
            LIMIT 10
            """,
            (since, since),
        )
        for row in cursor.fetchall():
            region_top.append(
                {
                    "country": row[0] or "Unknown",
                    "region": row[1] or "Unknown",
                    "city": row[2] or "Unknown",
                    "count": row[3] or 0,
                }
            )
    except Exception as e:
        print(f"Dashboard query error: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return stats, top_votes, logs, region_top, selected, period_label


@app.get("/view", response_class=HTMLResponse)
def viewDashboard(request: Request, pwd: str = "", period: str = "7d"):
    if pwd != VIEW_PWD:
        message = "密码错误" if pwd else ""
        return HTMLResponse(renderViewLogin(message), status_code=401 if pwd else 200)

    stats, top_votes, logs, region_top, selected, period_label = getDashboardData(period)
    return HTMLResponse(renderDashboardHtml(stats, top_votes, logs, region_top, selected, period_label, pwd), status_code=200)

@app.post("/api/rating/update", response_class=Response)
def updateRating(request: Request, response: Response,id: str = "",value: str = ""):
    if not checkReferer(request):
        response.status_code = 403
        return
    connection = None
    cursor = None
    
    if id == "" or value == "":
        response.status_code = 400
        return json.dumps({"code": 400, "message": "Bad Request"})
    value = float(value)
    if value < 1 or value > 5:
        response.status_code = 400
        return json.dumps({"code": 400, "message": "Bad Request"})
    # 将对应的id和value插入到数据库中
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()
        value = math.ceil(value)

        # 为对应的更新，若没有则新建
        sql = f"""
            INSERT INTO rating (id, "{value}") VALUES (%s, 1)
            ON CONFLICT (id) DO UPDATE SET
            "{value}" = rating."{value}" + 1, updated_at = CURRENT_TIMESTAMP;
        """
        cursor.execute(sql, (id,))
        connection.commit()
        logOperation(request, "rating_update", id, str(value), "ok")
        return json.dumps({"success": "true"})


    except psycopg2.Error as e:
        if connection:
            connection.rollback()  # 在发生错误时回滚事务
        print(f"Database error during rating update: {e}")
        logOperation(request, "rating_update", id, str(value), "error", str(e))
        return json.dumps({"code": 400, "message": "Database error during rating update."})
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
    


@app.post("/api/rating/cancel", response_class=Response)
def cancelRating(request: Request, response: Response, id: str = "", value: str = ""):
    if not checkReferer(request):
        response.status_code = 403
        return
    connection = None
    cursor = None

    if id == "" or value == "":
        response.status_code = 400
        return json.dumps({"code": 400, "message": "Bad Request"})
    value = float(value)
    if value < 1 or value > 5:
        response.status_code = 400
        return json.dumps({"code": 400, "message": "Bad Request"})

    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()
        value = math.ceil(value)

        sql = f"""
            UPDATE rating SET
            "{value}" = GREATEST("{value}" - 1, 0),
            updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING "1", "2", "3", "4", "5", created_at, updated_at;
        """
        cursor.execute(sql, (id,))
        result = cursor.fetchone()
        connection.commit()

        if result:
            rating_data = {
                "1": result[0],
                "2": result[1],
                "3": result[2],
                "4": result[3],
                "5": result[4],
                "createdAt": result[5].isoformat().replace('+00:00', 'Z'),
                "updatedAt": result[6].isoformat().replace('+00:00', 'Z'),
                "id": id
            }
        else:
            rating_data = {
                "1": 0,
                "2": 0,
                "3": 0,
                "4": 0,
                "5": 0,
                "createdAt": None,
                "updatedAt": None,
                "id": id
            }
        logOperation(request, "rating_cancel", id, str(value), "ok")
        return json.dumps({"success": "true", "rating": rating_data})

    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        print(f"Database error during rating cancel: {e}")
        logOperation(request, "rating_cancel", id, str(value), "error", str(e))
        response.status_code = 500
        return json.dumps({"code": 500, "message": "Database error during rating cancel."})

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.post("/api/vote/update", response_class=Response)
def updateVote(request: Request, response: Response, id: str = "", value: str = ""):
    if not checkReferer(request):
        response.status_code = 403
        return
    connection = None
    cursor = None

    if id == "" or value not in ["up", "down"]:
        response.status_code = 400
        return json.dumps({"code": 400, "message": "Bad Request"})

    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        sql = f"""
            INSERT INTO vote (id, {value}) VALUES (%s, 1)
            ON CONFLICT (id) DO UPDATE SET
            {value} = vote.{value} + 1, updated_at = CURRENT_TIMESTAMP;
        """
        cursor.execute(sql, (id,))
        connection.commit()
        logOperation(request, "vote_update", id, value, "ok")
        return json.dumps({"success": "true"})

    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        print(f"Database error during vote update: {e}")
        logOperation(request, "vote_update", id, value, "error", str(e))
        response.status_code = 500
        return json.dumps({"code": 500, "message": "Database error during vote update."})

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.post("/api/vote/cancel", response_class=Response)
def cancelVote(request: Request, response: Response, id: str = "", value: str = ""):
    if not checkReferer(request):
        response.status_code = 403
        return
    connection = None
    cursor = None

    if id == "" or value not in ["up", "down"]:
        response.status_code = 400
        return json.dumps({"code": 400, "message": "Bad Request"})

    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()
        counter_sql = "up = GREATEST(up - 1, 0)" if value == "up" else "down = GREATEST(down - 1, 0)"

        sql = f"""
            UPDATE vote SET
            {counter_sql},
            updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING up, down, created_at, updated_at;
        """
        cursor.execute(sql, (id,))
        result = cursor.fetchone()
        connection.commit()

        if result:
            vote_data = {
                "id": id,
                "up": result[0],
                "down": result[1],
                "createdAt": result[2].isoformat().replace('+00:00', 'Z'),
                "updatedAt": result[3].isoformat().replace('+00:00', 'Z'),
            }
        else:
            vote_data = {
                "id": id,
                "up": 0,
                "down": 0,
                "createdAt": None,
                "updatedAt": None,
            }
        logOperation(request, "vote_cancel", id, value, "ok")
        return json.dumps({"success": "true", "votes": vote_data})

    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        print(f"Database error during vote cancel: {e}")
        logOperation(request, "vote_cancel", id, value, "error", str(e))
        response.status_code = 500
        return json.dumps({"code": 500, "message": "Database error during vote cancel."})

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.get("/api/vote/info", response_class=Response)
def getVoteInfo(request: Request, response: Response, id: str = "default"):
    if not checkReferer(request):
        response.status_code = 403
        return
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()
        sql = "SELECT up, down, created_at, updated_at FROM vote WHERE id = %s"
        cursor.execute(sql, (id,))
        result = cursor.fetchone()
        if result:
            vote_data = {
                "id": id,
                "up": result[0],
                "down": result[1],
                "createdAt": result[2].isoformat().replace('+00:00', 'Z'),
                "updatedAt": result[3].isoformat().replace('+00:00', 'Z'),
            }
            return json.dumps({"votes": vote_data})
        else:
            default_vote = {
                "id": id,
                "up": 0,
                "down": 0,
                "createdAt": None,
                "updatedAt": None,
            }
            return json.dumps({"votes": default_vote})

    except psycopg2.Error as e:
        print(f"Database error during vote info retrieval: {e}")
        response.status_code = 500
        return json.dumps({"code": 500, "message": "Database error"})
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.get("/api/vote/batch_info", response_class=Response)
def getVoteBatchInfo(request: Request, response: Response, ids: str = ""):
    if not checkReferer(request):
        response.status_code = 403
        return

    if ids.strip() == "":
        response.status_code = 400
        return json.dumps({"code": 400, "message": "Bad Request"})

    raw_ids = [item.strip() for item in ids.split(",") if item.strip()]
    if len(raw_ids) == 0:
        response.status_code = 400
        return json.dumps({"code": 400, "message": "Bad Request"})
    if len(raw_ids) > MAX_BATCH_VOTE_IDS:
        response.status_code = 400
        return json.dumps({
            "code": 400,
            "message": f"Too many ids, max {MAX_BATCH_VOTE_IDS}"
        })

    # Keep original order while avoiding duplicate DB lookups.
    query_ids = list(dict.fromkeys(raw_ids))

    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()
        sql = "SELECT id, up, down, created_at, updated_at FROM vote WHERE id = ANY(%s)"
        cursor.execute(sql, (query_ids,))
        results = cursor.fetchall()

        by_id = {}
        for row in results:
            by_id[row[0]] = {
                "id": row[0],
                "up": row[1],
                "down": row[2],
                "createdAt": row[3].isoformat().replace('+00:00', 'Z'),
                "updatedAt": row[4].isoformat().replace('+00:00', 'Z'),
            }

        votes = []
        for vote_id in raw_ids:
            votes.append(by_id.get(vote_id, {
                "id": vote_id,
                "up": 0,
                "down": 0,
                "createdAt": None,
                "updatedAt": None,
            }))

        return json.dumps({"votes": votes})

    except psycopg2.Error as e:
        print(f"Database error during vote batch info retrieval: {e}")
        response.status_code = 500
        return json.dumps({"code": 500, "message": "Database error"})
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.get("/api/rating/info", response_class=Response)
def getRatingInfo(request: Request, response: Response, id: str = "default"):
    if not checkReferer(request):
        response.status_code = 403
        return
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()
        sql = 'SELECT "1", "2", "3", "4", "5", created_at, updated_at FROM rating WHERE id = %s'
        cursor.execute(sql, (id,))
        result = cursor.fetchone()
        
        if result:
            rating_data = {
                "1": result[0],
                "2": result[1],
                "3": result[2],
                "4": result[3],
                "5": result[4],
                "createdAt": result[5].isoformat().replace('+00:00', 'Z'),
                "updatedAt": result[6].isoformat().replace('+00:00', 'Z'),
                "id": id
            }
            return json.dumps({"rating": rating_data})
        else:
            # If no record is found, return a default structure with all counts as 0.
            default_rating = {
                "1": 0,
                "2": 0,
                "3": 0,
                "4": 0,
                "5": 0,
                "createdAt": None,
                "updatedAt": None,
                "id": id
            }
            return json.dumps({"rating": default_rating})

    except psycopg2.Error as e:
        print(f"Database error during rating info retrieval: {e}")
        response.status_code = 500
        return json.dumps({"code": 500, "message": "Database error"})
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.get("/", response_class=Response)
def index():
    return "Hello World"


@app.get("/api/init", response_class=Response)
def init(pwd: str = ""):
    if pwd != amdinPWD:
        return json.dumps({"code": 401, "message": "Unauthorized"})

    # 链接数据库初始化
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        # 创建两张数据表
        # 一张是 rating，包括 id (string) 和 value (int)
        # 另一张是 vote，包括 id (string) 和 up (int) 和 down (int)
        sql = """
            CREATE TABLE IF NOT EXISTS rating (
                id VARCHAR(255) PRIMARY KEY,
                "1" INTEGER NOT NULL DEFAULT 0,
                "2" INTEGER NOT NULL DEFAULT 0,
                "3" INTEGER NOT NULL DEFAULT 0,
                "4" INTEGER NOT NULL DEFAULT 0,
                "5" INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS vote (
                id VARCHAR(255) PRIMARY KEY,
                up INTEGER NOT NULL DEFAULT 0,
                down INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS operation_log (
                id SERIAL PRIMARY KEY,
                action VARCHAR(64) NOT NULL,
                item_id VARCHAR(255) NOT NULL,
                value VARCHAR(64) NOT NULL,
                status VARCHAR(32) NOT NULL,
                message TEXT,
                ip VARCHAR(128) NOT NULL,
                ip_country VARCHAR(128) NOT NULL DEFAULT 'Unknown',
                ip_region VARCHAR(128) NOT NULL DEFAULT 'Unknown',
                ip_city VARCHAR(128) NOT NULL DEFAULT 'Unknown',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """
        cursor.execute(sql)
        connection.commit()
        return json.dumps({"code": 200, "message": "Database tables created successfully"})
    except psycopg2.Error as e:
        if connection:
            connection.rollback()  # 在发生错误时回滚事务
        print(f"Database error during initialization: {e}")
        return json.dumps({"code": 500, "message": f"Database initialization error: {str(e)}"})
    except Exception as e:
        print(f"General error during initialization: {e}")
        return json.dumps({"code": 500, "message": f"An unexpected error occurred during initialization: {str(e)}"})
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def checkReferer(request):
    referer = request.headers.get("referer")
    # print(request.headers)
    if not referer:
        return False
    hostname = urlparse(referer).hostname
    # 检查主机名是否在允许的域名列表中
    for allowed_host in allowedHosts:
        if hostname.endswith(allowed_host):
            return True


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", reload=True)
    # uvicorn.run("main:app", host="0.0.0.0", reload=True,port=18081)
