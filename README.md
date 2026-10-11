# MyEnglishTeacher

AI 英语私教 App —— 覆盖初中 / 高中 / 大学阶段，按学段分级、按主题学习。

## 两大核心功能

1. **词句输入**：背单词（SRS 间隔重复）、典型句型库、精选影视剧台词
2. **输出训练**：AI 虚拟老师场景化模拟对话，实时纠错讲解；专项听写练习，错误自动入复习闭环

## 文档

- [产品与技术设计 v0.2（已确认）](docs/DESIGN.md)

## 技术栈

FastAPI · PostgreSQL · Next.js + TypeScript · Docker Compose · 火山方舟 LLM · edge-tts

## 本地开发（M0 已就绪）

```bash
docker compose up -d --build
# frontend  http://127.0.0.1:3005
# backend   http://127.0.0.1:8005/api/v1/health
# postgres  127.0.0.1:5435
```

## 数据初始化

```bash
# 词库 CSV 不入库；首次需下载 ECDICT 后导入
docker compose exec met-backend python -m scripts.import_ecdict --csv /app/scripts/seed/ecdict.csv --g7 /app/scripts/seed/g7

# M2/M3 内置内容（幂等）
docker compose exec met-backend python -m scripts.import_content
docker compose exec met-backend python -m scripts.import_scenarios
```

## 里程碑

- [x] M0 脚手架（compose / FastAPI / Next.js / CI）
- [x] M1 背单词：ECDICT 8,755 词导入（初一 315/中考 1368/高考 2110/四级 1632/六级考研 2060/雅思 1270）、手机一键登录、SRS 单词卡、单词听写、TTS 发音（有道真人 + edge-tts）、收藏/打卡
- [x] M2 句型 & 《老友记》台词：24 个七年级句型、20 条 Friends 精选台词（含出处与语言点）、卡片学习/例句 TTS/收藏、级别过滤与搜索、管理员后台 CRUD
- [x] M3 AI 虚拟老师对话：6 个七年级场景卡、SSE 真流式回复、结构化纠错（7 类错误）、错句复习本、结课报告、每日轮次限额、LLM token/延迟日志
- [ ] M4 专项听写
- [ ] M5 AI 口语发音评分 + PWA 打磨

---

_项目状态：M3 已完成，M4（专项听写）待开始。_
