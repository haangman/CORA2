/* 노드 패리티 러너: report_logic.js 를 로드해 입력 벡터에 대한 태그를 출력한다.
 * argv[2] = report_logic.js 절대경로, argv[3] = 입력 JSON 경로.
 */
const fs = require("fs");
const L = require(process.argv[2]);
const inp = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const cfg = inp.cfg;

const out = inp.vectors.map((v) => {
  switch (v.kind) {
    case "size":
      return L.sizeTag(v.loc, cfg.size);
    case "recency":
      return L.recencyTag(v.rd, cfg.recency);
    case "author":
      return L.authorPatternTag(v.ac, cfg.author_pattern);
    case "vol":
      return L.volatilityTag(v.cm, cfg.volatility, new Set(v.internalIds));
    default:
      return null;
  }
});
process.stdout.write(JSON.stringify(out));
