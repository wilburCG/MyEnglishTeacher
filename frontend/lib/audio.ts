import { getToken } from "./api";

// audio 标签不能带 Authorization 头，用鉴权 fetch 拿 blob 再本地播放
export async function playWord(wordId: number, accent: "us" | "uk" = "us") {
  const resp = await fetch(
    `/api/v1/audio/word/${wordId}?accent=${accent}`,
    { headers: { Authorization: `Bearer ${getToken() ?? ""}` } },
  );
  if (!resp.ok) throw new Error("发音加载失败");
  return playBlob(await resp.blob());
}

export async function playSentence(text: string, accent: "us" | "uk" = "us") {
  const url = `/api/v1/audio/sentence?accent=${accent}&text=${encodeURIComponent(
    text,
  )}`;
  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${getToken() ?? ""}` },
  });
  if (!resp.ok) throw new Error("发音加载失败");
  return playBlob(await resp.blob());
}

const current: { url: string }[] = [];

export async function playBlob(blob: Blob) {
  const url = URL.createObjectURL(blob);
  current.forEach((c) => URL.revokeObjectURL(c.url));
  current.length = 0;
  current.push({ url });
  const audio = new Audio(url);
  await audio.play().catch(() => undefined);
  audio.onended = () => URL.revokeObjectURL(url);
  return audio;
}
