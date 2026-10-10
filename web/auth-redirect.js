/* Keep Open WebUI SPA session-expiry/logout navigation on our account login. */
(() => {
  function redirectAuth() {
    if (location.pathname === '/auth' || location.pathname === '/auth/') {
      location.replace('/login');
    }
  }
  redirectAuth();
  addEventListener('popstate', redirectAuth);
  // SvelteKit navigation uses pushState without a full document request.
  setInterval(redirectAuth, 150);
})();
