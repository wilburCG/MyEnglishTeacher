export type Level =
  | "junior-g7"
  | "junior"
  | "senior"
  | "cet4"
  | "cet6"
  | "ielts";

export const LEVELS: { value: Level; label: string; sub: string }[] = [
  { value: "junior-g7", label: "初一", sub: "人教版七年级 · 入门" },
  { value: "junior", label: "初中", sub: "中考 1600 词" },
  { value: "senior", label: "高中", sub: "高考 3500 词" },
  { value: "cet4", label: "大学四级", sub: "CET-4" },
  { value: "cet6", label: "六级/考研", sub: "CET-6 / 考研" },
  { value: "ielts", label: "雅思", sub: "IELTS 5.5+" },
];

export const levelLabel = (v: string) =>
  LEVELS.find((l) => l.value === v)?.label ?? v;
