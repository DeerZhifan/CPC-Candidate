// 把 index.html 里通过 <script src="xxx.js"> 引入的题库文件，内联打包成一个
// 自包含的单文件 HTML（exam-app.html），供 Claude Artifact 发布使用
// （Artifact 只托管单个文件，无法像本地 http.server 那样同目录加载其他 .js 文件）。
//
// 用法：node build-standalone.js
"use strict";
const fs = require("fs");
const path = require("path");

const DIR = __dirname;
const SRC = path.join(DIR, "index.html");
const OUT = path.join(DIR, "exam-app.html");

let html = fs.readFileSync(SRC, "utf8");

const reScriptSrc = /<script src="([^"]+\.js)"><\/script>/g;
let count = 0;
html = html.replace(reScriptSrc, (m, file) => {
  const filePath = path.join(DIR, file);
  const content = fs.readFileSync(filePath, "utf8");
  count++;
  return `<script>\n/* ==== inlined: ${file} ==== */\n${content}\n</script>`;
});

fs.writeFileSync(OUT, html, "utf8");
console.log(`内联了 ${count} 个脚本文件，已写入 ${OUT}（${(fs.statSync(OUT).size / 1024).toFixed(0)} KB）`);
console.log(
  "\n发布到 Claude Artifact 时，建议声明 downloads 能力：capabilities: { downloads: true }。\n" +
  "  · 答题进度、同步码、错题分析都在浏览器本地运行，不依赖任何能力；\n" +
  "  · 只有【进度同步 → 导出备份文件】需要它——artifact 预览里页面自身发起的下载会被沙箱拦掉，\n" +
  "    声明后走 claude.use(\"downloads\") 由查看者确认保存；未声明时该按钮会自动退回 Blob 下载（在\n" +
  "    artifact 里可能无声失败），同步码与同步链接不受影响。"
);
