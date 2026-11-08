import { useEffect, useId, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { Check, ChevronDown } from 'lucide-react';

export type SelectOption = { value: string; label: string };

export function ThemeSelect({ label, name, value, defaultValue, options, onChange, invalid = false }: {
  label: string;
  name?: string;
  value?: string;
  defaultValue?: string;
  options: SelectOption[];
  onChange?: (value: string) => void;
  invalid?: boolean;
}) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [internal, setInternal] = useState(defaultValue ?? options[0]?.value ?? '');
  const [open, setOpen] = useState(false);
  const selected = value ?? internal;
  const currentIndex = Math.max(0, options.findIndex(option => option.value === selected));
  const [activeIndex, setActiveIndex] = useState(currentIndex);

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [open]);

  const choose = (index: number) => {
    const option = options[index];
    if (!option) return;
    setInternal(option.value);
    onChange?.(option.value);
    setOpen(false);
    trigger.current?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Escape' && open) { event.preventDefault(); setOpen(false); return; }
    if (event.key === 'Tab') { setOpen(false); return; }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex(index => open
        ? (index + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length
        : Math.max(0, Math.min(options.length - 1, currentIndex + (event.key === 'ArrowDown' ? 1 : -1))));
      setOpen(true);
    } else if (event.key === 'Home' && open) { event.preventDefault(); setActiveIndex(0); }
    else if (event.key === 'End' && open) { event.preventDefault(); setActiveIndex(options.length - 1); }
    else if ((event.key === 'Enter' || event.key === ' ') && open) { event.preventDefault(); choose(activeIndex); }
    else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && event.key !== ' ') {
      const found = options.findIndex(option => option.label.toLowerCase().startsWith(event.key.toLowerCase()));
      if (found >= 0) { setActiveIndex(found); setOpen(true); }
    }
  };

  return <div className="theme-select" ref={root}>
    <span className="theme-select-label" id={`${id}-label`}>{label}</span>
    {name && <input type="hidden" name={name} value={selected} />}
    <button ref={trigger} type="button" className="theme-select-trigger" role="combobox" aria-labelledby={`${id}-label`} aria-controls={`${id}-options`} aria-expanded={open} aria-invalid={invalid || undefined} aria-haspopup="listbox" aria-activedescendant={open ? `${id}-option-${activeIndex}` : undefined} onClick={() => { setActiveIndex(currentIndex); setOpen(!open); }} onKeyDown={onKeyDown}>
      <span>{options[currentIndex]?.label || 'Choose an option'}</span><ChevronDown size={17} aria-hidden="true" />
    </button>
    {open && <div id={`${id}-options`} className="theme-select-options" role="listbox" aria-labelledby={`${id}-label`}>
      {options.map((option, index) => <div key={option.value} id={`${id}-option-${index}`} className={`theme-select-option ${index === activeIndex ? 'active' : ''}`} role="option" aria-selected={option.value === selected} onMouseEnter={() => setActiveIndex(index)} onClick={() => choose(index)}>
        <span>{option.label}</span>{option.value === selected && <Check size={16} aria-hidden="true" />}
      </div>)}
    </div>}
  </div>;
}
