import { useEffect, useRef, useState, type FormEvent } from 'react';
import SliderCaptchaField from './SliderCaptchaField';
import { api } from './api';

function Shield({ small = false }: { small?: boolean }) {
  return <svg width={small ? 17 : 23} height={small ? 17 : 23} viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/><path d="m8.5 11.8 2.3 2.3 4.8-5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}
export default function App() {
  const [tab, setTab] = useState(0);
  const [token, setToken] = useState('');
  const [captchaKey, setCaptchaKey] = useState(0);
  const [status, setStatus] = useState<'idle' | 'verified' | 'success'>('idle');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo123!');
  const expiryTimer = useRef<ReturnType<typeof setTimeout>>();
  const clearToken = () => { clearTimeout(expiryTimer.current); setToken(''); setStatus('idle'); };
  useEffect(() => () => clearTimeout(expiryTimer.current), []);
  const verified = (nextToken: string, expiresIn: number) => {
    clearTimeout(expiryTimer.current);
    setToken(nextToken); setStatus('verified'); setMessage('');
    expiryTimer.current = setTimeout(() => {
      clearToken(); setMessage('验证凭证已过期，请重新完成拼图。'); setCaptchaKey(key => key + 1);
    }, expiresIn * 1000);
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!token || busy) return;
    setBusy(true); setMessage('');
    const credential = token;
    clearTimeout(expiryTimer.current);
    setToken(''); // Never retry a consumed credential, including failed login attempts.
    try {
      const result = await api<{ message: string }>('/api/demo/login/', { username, password, captchaToken: credential });
      setStatus('success'); setMessage(result.message);
    } catch (error) {
      setStatus('idle'); setCaptchaKey(key => key + 1);
      setMessage(error instanceof Error ? error.message : '登录失败，请重试。');
    } finally { setBusy(false); }
  };
  return <div className="site-shell">
    <header className="site-header"><a className="brand" href="/" aria-label="身份验证首页"><span className="brand-mark"><Shield /></span><span>身份验证<span className="brand-subtitle">IDENTITY GATEWAY</span></span></a><span className="header-badge"><span className="live-dot" />DRF × React</span></header>
    <main>
      <div className="intro"><span className="eyebrow">SECURE ACCESS</span><h1>简单一步，安全连接。</h1><p>完成身份验证，开启您的服务。</p></div>
      <section className="login-card" aria-label="登录与滑块验证">
        <aside className="visual-panel"><div className="orb orb-one"/><div className="orb orb-two"/>
          <div className="illustration"><div className="floating-chip"><span>✓</span>服务端安全校验</div><div className="shield-tile"><Shield /></div><div className="tiny-tile tile-a">•••</div><div className="tiny-tile tile-b">✧</div></div>
          <div className="visual-copy"><span className="visual-kicker">为每一次访问，多一层守护</span><h2>验证的是身份，<br/>连接的是信任。</h2><p>轻轻滑动，确认是您本人。<br/>让便捷与安全，同时在线。</p></div>
          <div className="visual-bottom"><Shield small /><span>一次验证 · 短期有效 · 防止重放</span></div>
        </aside>
        <div className="form-panel">
          <div className="form-heading"><h2>欢迎登录</h2><span>SLIDER CAPTCHA DEMO</span></div>
          <div className="tabs" role="tablist" aria-label="登录身份">{['自然人', '法人', '代理机构'].map((label, index) => <button type="button" role="tab" aria-selected={tab === index} key={label} className={tab === index ? 'active' : ''} onClick={() => { setTab(index); clearToken(); setMessage(''); setCaptchaKey(key => key + 1); }}>{label}登录</button>)}</div>
          <form onSubmit={submit}>
            <label className="field-label" htmlFor="username">{tab === 0 ? '账号' : tab === 1 ? '法人账号' : '机构账号'}</label>
            <div className="input-wrap"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.2"/><path d="M5.5 20v-2a6.5 6.5 0 0 1 13 0v2"/></svg><input id="username" autoComplete="username" required value={username} onChange={event => setUsername(event.target.value)}/></div>
            <label className="field-label" htmlFor="password">密码</label>
            <div className="input-wrap"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><path d="M12 14v3"/></svg><input id="password" type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)}/></div>
            <div className="verification-heading"><span className="field-label">安全验证</span><span className={status === 'verified' ? 'status verified' : 'status'}><span className="status-dot"/>{status === 'verified' ? '验证通过' : status === 'success' ? '凭证已消费' : '请完成拼图'}</span></div>
            {status !== 'success' ? <div className="captcha-frame"><SliderCaptchaField key={`${tab}-${captchaKey}`} onVerified={verified} onReset={clearToken} onError={setMessage}/></div> : <div className="success-panel"><Shield/><strong>演示登录成功</strong><span>一次性验证凭证已安全消费</span><button type="button" onClick={() => { clearToken(); setMessage(''); setCaptchaKey(key => key + 1); }}>重新体验 ↗</button></div>}
            <div className={`feedback ${status === 'success' ? 'success-feedback' : ''}`} role="status" aria-live="polite">{message}</div>
            <button className="submit-button" disabled={!token || busy} type="submit"><span>{busy ? '正在验证…' : '安全登录'}</span><span aria-hidden="true">→</span></button>
            <p className="demo-note">演示账号 <code>demo</code><span> / </span>密码 <code>demo123!</code></p>
          </form>
        </div>
      </section>
      <div className="trust-row"><span><Shield small/>服务端生成与校验</span><span><span className="small-circle">✓</span>一次性凭证</span><span><span className="small-circle">⌁</span>原生 rc-slider-captcha</span></div>
    </main>
    <footer><span>仅用于接口联调演示，不会建立真实登录会话</span><span>POWERED BY DJANGO REST FRAMEWORK</span></footer>
  </div>;
}
