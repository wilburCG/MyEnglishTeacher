import { api } from "./api";

export type Pattern = {
  id: number;
  level: string;
  theme: string;
  unit: string | null;
  template: string;
  func_zh: string;
  grammar_point: string | null;
  explanation_zh: string | null;
  examples: { en: string; zh: string }[];
  favorite: boolean;
};

export type MovieLine = {
  id: number;
  show: string;
  season: number | null;
  episode: number | null;
  character: string;
  text_en: string;
  text_zh: string;
  level: string;
  theme: string | null;
  note_zh: string | null;
  favorite: boolean;
};

export async function listPatterns(
  opts: { level?: string; includeAll?: boolean } = {},
): Promise<Pattern[]> {
  const params = new URLSearchParams();
  if (opts.level) params.set("level", opts.level);
  if (opts.includeAll) params.set("include_all_levels", "true");
  const qs = params.toString();
  const data = await api<{ patterns: Pattern[] }>(
    `/patterns${qs ? `?${qs}` : ""}`,
  );
  return data.patterns;
}

export async function listLines(
  opts: {
    level?: string;
    q?: string;
    character?: string;
    includeAll?: boolean;
  } = {},
): Promise<MovieLine[]> {
  const params = new URLSearchParams();
  if (opts.level) params.set("level", opts.level);
  if (opts.q) params.set("q", opts.q);
  if (opts.character) params.set("character", opts.character);
  if (opts.includeAll) params.set("include_all_levels", "true");
  const qs = params.toString();
  const data = await api<{ lines: MovieLine[] }>(
    `/lines${qs ? `?${qs}` : ""}`,
  );
  return data.lines;
}

export async function setContentFavorite(
  itemType: "pattern" | "line",
  itemId: number,
  favorite: boolean,
) {
  return api("/content/favorite", {
    method: "POST",
    body: JSON.stringify({
      item_type: itemType,
      item_id: itemId,
      favorite,
    }),
  });
}

export function episodeTag(l: MovieLine): string {
  if (l.season && l.episode) return `S${String(l.season).padStart(2, "0")}E${String(l.episode).padStart(2, "0")}`;
  if (l.season) return `S${String(l.season).padStart(2, "0")}`;
  return "经典片段";
}
