import { useState, useEffect, useRef } from 'react';

export type Theme = 'dark' | 'light';

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  });

  const buttonRef = useRef<HTMLButtonElement | null>(null);

  // Apply theme on initial mount only — subsequent changes go through toggleTheme directly.
  useEffect(() => {
    applyTheme(theme);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!document.startViewTransition || prefersReducedMotion) {
      setTheme(nextTheme);
      applyTheme(nextTheme);
      return;
    }

    const button = buttonRef.current;
    if (!button) {
      setTheme(nextTheme);
      applyTheme(nextTheme);
      return;
    }

    const rect = button.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;

    const endRadius = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y),
    );

    // Add a helper class before the transition so CSS can set z-indices
    // correctly for both expand (→ light) and collapse (→ dark) directions.
    document.documentElement.classList.add('theme-transitioning');
    if (nextTheme === 'dark') {
      document.documentElement.classList.add('to-dark');
    }

    const transition = document.startViewTransition(() => {
      // Apply data-theme AND React state synchronously inside the callback.
      // The browser will capture the "new" snapshot after this function returns.
      applyTheme(nextTheme);
      setTheme(nextTheme);
    });

    transition.ready.then(() => {
      const expand = [`circle(0px at ${x}px ${y}px)`, `circle(${endRadius}px at ${x}px ${y}px)`];
      const collapse = [...expand].reverse();

      document.documentElement.animate(
        { clipPath: nextTheme === 'light' ? expand : collapse },
        {
          duration: 500,
          easing: 'ease-in-out',
          pseudoElement: nextTheme === 'light'
            ? '::view-transition-new(root)'
            : '::view-transition-old(root)',
        },
      );
    });

    transition.finished.finally(() => {
      document.documentElement.classList.remove('theme-transitioning', 'to-dark');
    });
  };

  return { theme, toggleTheme, buttonRef };
}
