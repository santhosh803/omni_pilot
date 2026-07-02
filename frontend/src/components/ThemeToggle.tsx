import React from 'react';
import { Sun, Moon } from 'lucide-react';
import type { Theme } from '../hooks/useTheme';

interface ThemeToggleProps {
  theme: Theme;
  onToggle: () => void;
  buttonRef: React.RefObject<HTMLButtonElement | null>;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ theme, onToggle, buttonRef }) => {
  return (
    <button
      ref={buttonRef}
      className="theme-toggle-btn"
      onClick={onToggle}
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-label="Toggle Theme"
    >
      {theme === 'dark' ? (
        <Sun size={16} className="theme-icon sun" />
      ) : (
        <Moon size={16} className="theme-icon moon" />
      )}
    </button>
  );
};
export default ThemeToggle;
