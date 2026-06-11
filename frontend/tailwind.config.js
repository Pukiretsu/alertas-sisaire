/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        air: {
          50: '#f5fbff',
          100: '#e7f4ff',
          500: '#2563eb',
          900: '#0f172a',
        },
      },
      boxShadow: {
        soft: '0 20px 55px rgba(15, 23, 42, 0.12)',
      },
    },
  },
  plugins: [],
};
