/* Bootstrap Open WebUI only after signing in as the current Bifrost identity. */
(() => {
  const login = 'https://d.58nft.net:9461/login?return=model-bridge';
  const permissions = 'https://d.58nft.net/permissions?app=model-bridge';
  function stop(response) {
    localStorage.removeItem('token');
    if (response.status === 401 || response.status === 403) location.replace(response.status === 403 ? permissions : login);
    else {
      const show = () => { const panel=document.createElement('div');panel.style.cssText='position:fixed;inset:0;z-index:9999;background:Canvas;color:CanvasText;display:grid;place-content:center;gap:20px;padding:24px';const message=document.createElement('p');message.textContent='暂时无法验证彩虹桥登录，请重试。';const retry=document.createElement('button');retry.textContent='重新验证';retry.onclick=()=>location.reload();panel.append(message,retry);document.body.append(panel); };
      if(document.body)show();else addEventListener('DOMContentLoaded',show,{once:true});
    }
    return new Promise(() => {});
  }
  let userId, userRole;
  window.workspaceReady = (async () => {
    const response = await fetch('/api/v1/auths/signin', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:'',password:''})}).catch(()=>null);
    if (!response?.ok) return stop(response || {status:503});
    const session = await response.json();
    let previous=localStorage.getItem('workspace-user-id');
    if(!previous){try{previous=JSON.parse(atob((localStorage.getItem('token')||'').split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))).id}catch{}}
    if(previous && previous !== session.id){
      const theme=localStorage.getItem('theme');localStorage.clear();sessionStorage.clear();if(theme)localStorage.setItem('theme',theme);
    }
    userId = session.id; userRole = session.role;
    localStorage.setItem('token', session.token);
    localStorage.setItem('workspace-user-id', session.id);
    if(location.pathname==='/auth'||location.pathname==='/auth/'||location.pathname==='/login')history.replaceState(null,'','/');
  })();
  let checking=false;
  async function check() {
    if (checking || document.hidden || !userId) return;
    checking=true;
    try {
      const response=await fetch('/api/v1/auths/', {credentials:'include',headers:{Authorization:'Bearer '+(localStorage.getItem('token')||'')}});
      if(!response.ok){if(response.status===401)location.reload();else if(response.status===403)stop(response);return;}
      const session=await response.json();if(session.id!==userId||session.role!==userRole)location.reload();
    } catch { /* Retry on focus or the next interval; API authorization stays server-side. */ }
    finally {checking=false;}
  }
  addEventListener('focus',check);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();});
  setInterval(check,30000);
  function managedNavigation() {
    if(/^\/admin\/users(?:\/|$)/.test(location.pathname))location.replace('https://d.58nft.net/admin');
    else if(/^\/auth\/?$/.test(location.pathname))location.replace('/');
  }
  addEventListener('popstate',managedNavigation);
  setInterval(managedNavigation,500);
})();
