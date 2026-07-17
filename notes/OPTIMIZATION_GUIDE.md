# 考点页优化规范

本目录的 HTML 以对应科目的四色笔记 PDF 为内容基线。优化分为两条独立验收线：

1. **内容完整**：PDF 逐页 OCR 后按章定位；候选遗漏必须回看原页确认，不能把 OCR 结果直接当成正确文本。
2. **表达有效**：视觉组件只用于呈现关系、顺序、差异、公式或决策路径，不为“好看”重复堆叠内容。

## 内容核对

```powershell
python tools/notes_audit.py ocr --subject law-fort
python tools/notes_audit.py report --subject law-fort
```

可用科目标识：`law-fort`（法规）、`eco-war`（经济）、`cmd-core`（管理）、`all`。OCR 与报告缓存位于 `tmp/notes-audit/`，不提交 Git。

覆盖报告先给出“编号知识点检查”，用于发现类似 `3.2.4` 的整段缺失；随后列出的“候选遗漏”包含换行、同义改写和 OCR 误差造成的误报。补充 HTML 前必须完成三项确认：原 PDF 确实存在、当前 HTML 未以其他表述覆盖、内容属于考点知识而非页眉页脚或重复例题。

## 视觉形式选择

| 信息关系 | 优先形式 | 适用示例 |
|---|---|---|
| 有明确先后顺序 | `.flow` | 建设程序、审批程序、质量监督程序 |
| 以时间节点为主 | `.timeline` | 期限、保修、诉讼时效、付款节点 |
| 两类以上并列辨析 | `.compare-grid` | 单利/复利、抵押/质押/留置 |
| 公式与适用场景 | `.formula-grid` / `.formula-card` | 资金等值、财务指标、计价公式 |
| 层级或短口诀 | `.memory-chain` | 法的效力层级、责任主体 |
| 条件判断与分支 | `.decision-tree` | 裁决机关、许可条件、风险分配 |
| 计划—执行—反馈闭环 | `.cycle` | 动态控制、PDCA、持续改进 |

每个视觉块应紧邻其原始考点，并保留可检索的文字。表格适用于需要逐字段精确比较的内容；若只表达顺序，不应继续用表格代替流程。

## 页面级验收

- 原有考点、真题、返回链接和展开/收起功能仍可用。
- 320px 宽度下正文不横向溢出；宽表放在可横向滚动容器内。
- 颜色不是唯一的信息载体，关键关系仍有文字、顺序或标签。
- 一页内同类关系使用同一种组件；视觉块数量以帮助理解为限。
- 共享资源只通过 `../shared/notes-enhance.css` 和 `../shared/notes-enhance.js` 引入一次。

全量检查共享资源、本地链接、HTML 标签嵌套和流程节点结构：

```powershell
python tools/notes_audit.py validate --subject all
python tools/notes_audit.py inventory --subject all
```

新增章节页后，可执行 `python tools/inject_notes_assets.py`；脚本幂等，不会重复插入已存在的共享 CSS/JS 引用。
