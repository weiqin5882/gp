# 跨市场映射系统 1.0（Python 半自动化）

把“美股映射 A 股”固化为流程：

1. **数据源模块**：固定记录 TSLA 指标。
2. **情绪判定模块**：趋势扩张 / 震荡 / 回撤。
3. **产业映射模块**：固定三大映射池（季度更新）。
4. **评分过滤模块**：10 分制，`>=6` 才开仓观察。
5. **执行与复盘模块**：T 日评分，T+1 只看预设池，T+3/T+5 统一平仓。

## 文件结构

- `mapping_system.py`：主程序（CLI + 核心评分函数）
- `web_app.py`：网页版服务（无第三方依赖）
- `config/pools.json`：固定映射池配置
- `data/`：输入数据（手工或脚本生成）
- `records/review_log.csv`：复盘记录

## 输入格式

### `data/tsla_daily.csv`

必需字段：

- `date`（YYYY-MM-DD）
- `close`
- `pct_change`（单日涨跌幅，%）
- `daily_volatility`（单日波动率，%）
- `vol_3d`（3日波动率，%）
- `volume`
- `volume_ma20`
- `breakout`（true/false）
- `ma5`

### `data/ashare_daily.csv`

必需字段：

- `date`
- `ticker`
- `name`
- `pool`
- `pct_change`
- `volume`
- `volume_ma5`

### `data/events.json`

```json
{
  "2026-02-20": {"event_intensity": 2}
}
```

## 使用（命令行）

```bash
python mapping_system.py --date 2026-02-20
```

可选参数：

```bash
python mapping_system.py \
  --date 2026-02-20 \
  --tsla-csv data/tsla_daily.csv \
  --ashare-csv data/ashare_daily.csv \
  --events-json data/events.json \
  --pools-json config/pools.json \
  --log-csv records/review_log.csv
```

## 使用（网页版）

```bash
python web_app.py
```

默认监听 `0.0.0.0:3000`，访问：`http://127.0.0.1:3000`。

也支持通过环境变量覆盖（便于服务器部署）：

```bash
HOST=0.0.0.0 PORT=3000 python web_app.py
```

- 页面输入评估日期后，自动计算 10 分制评分。
- 页面显示执行建议和重点观察标的。
- 当前版本读取本地 `data/` 示例数据，可接日终自动化数据更新。

> 半自动化建议：日终用脚本拉取 TSLA/A 股数据并覆盖 `data/` 文件，本程序负责统一评分、过滤和日志。
