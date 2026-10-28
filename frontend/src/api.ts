export type Challenge = {
  challengeId: string; bgUrl: string; puzzleUrl: string;
  bgSize: { width: number; height: number };
  puzzleSize: { width: number; height: number; top: number; left: number };
  expiresIn: number; purpose: string;
};
export type Verification = { success: true; captchaToken: string; expiresIn: number };
export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body), cache: 'no-store', signal,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.detail || '请求失败，请稍后重试。');
  return data as T;
}
