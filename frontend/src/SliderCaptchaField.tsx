import { useEffect, useRef, useState } from 'react';
import SliderCaptcha, { type VerifyParam } from 'rc-slider-captcha';
import { api, type Challenge, type Verification } from './api';

type Props = {
  purpose?: string;
  onVerified: (token: string, expiresIn: number) => void;
  onReset: () => void;
  onError?: (message: string) => void;
};

/** Resize both images together; normalize puzzle movement back to native pixels. */
export default function SliderCaptchaField({ purpose = 'login', onVerified, onReset, onError }: Props) {
  const [challenge, setChallenge] = useState<Challenge>();
  const [availableWidth, setAvailableWidth] = useState(320);
  const container = useRef<HTMLDivElement>(null);
  const challengeRef = useRef<Challenge>();
  const controller = useRef<AbortController>();
  const generation = useRef(0);
  const callbacks = useRef({ onVerified, onReset, onError });
  callbacks.current = { onVerified, onReset, onError };
  const nativeSize = challenge?.bgSize ?? { width: 320, height: 160 };
  const nativePuzzle = challenge?.puzzleSize ?? { width: 60, height: 160, top: 0, left: 0 };
  const scale = Math.min(1, availableWidth / nativeSize.width);
  const scaleRef = useRef(scale);
  scaleRef.current = scale;
  useEffect(() => {
    const element = container.current!;
    const observer = new ResizeObserver(([entry]) => setAvailableWidth(Math.max(1, entry.contentRect.width)));
    observer.observe(element);
    return () => { observer.disconnect(); generation.current += 1; controller.current?.abort(); };
  }, []);
  const request = async () => {
    const version = ++generation.current;
    controller.current?.abort();
    controller.current = new AbortController();
    challengeRef.current = undefined;
    callbacks.current.onReset();
    try {
      const data = await api<Challenge>(`/api/captcha/challenge/?purpose=${encodeURIComponent(purpose)}`, undefined, controller.current.signal);
      if (version !== generation.current) throw new Error('验证码已刷新。');
      challengeRef.current = data;
      setChallenge(data);
      return { bgUrl: data.bgUrl, puzzleUrl: data.puzzleUrl };
    } catch (error) {
      if (version === generation.current && !(error instanceof DOMException && error.name === 'AbortError'))
        callbacks.current.onError?.(error instanceof Error ? error.message : '验证码加载失败。');
      throw error;
    }
  };
  const onVerify = async (values: VerifyParam) => {
    const current = challengeRef.current;
    const version = generation.current;
    if (!current) throw new Error('请刷新验证码。');
    try {
      const result = await api<Verification>('/api/captcha/verify/', {
        challengeId: current.challengeId,
        ...values,
        x: values.x / scaleRef.current,
        // x is PUZZLE movement, not sliderOffsetX. trail remains viewport [x,y] pairs.
      }, controller.current?.signal);
      if (version !== generation.current) throw new Error('验证码已刷新。');
      callbacks.current.onVerified(result.captchaToken, result.expiresIn);
      return result;
    } catch (error) {
      if (version === generation.current) {
        callbacks.current.onReset();
        callbacks.current.onError?.(error instanceof Error ? error.message : '验证失败。');
      }
      throw error;
    }
  };
  return <div ref={container} style={{ width: '100%' }}><SliderCaptcha request={request} onVerify={onVerify}
    bgSize={{ width: nativeSize.width * scale, height: nativeSize.height * scale }}
    puzzleSize={{ width: nativePuzzle.width * scale, height: nativePuzzle.height * scale,
      top: nativePuzzle.top * scale, left: nativePuzzle.left * scale }}
    autoRefreshOnError
    tipText={{ default: '向右拖动滑块，完成拼图', success: '验证通过', error: '请再试一次' }}
    style={{ '--rcsc-primary': '#3d63dd', '--rcsc-success': '#25826b', '--rcsc-control-height': '44px' }} /></div>;
}
