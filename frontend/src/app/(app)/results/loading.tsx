export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="skeleton h-8 w-64 rounded-lg" />
      <div className="skeleton mt-3 h-4 w-96 max-w-full rounded-full" />
      <ul className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <li key={i} className="card p-4">
            <div className="skeleton h-3 w-20 rounded-full" />
            <div className="skeleton mt-2 h-7 w-12 rounded-lg" />
          </li>
        ))}
      </ul>
      <div className="skeleton mt-8 h-28 w-full rounded-2xl" />
      <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <li key={i} className="card p-5">
            <div className="flex gap-3">
              <div className="skeleton h-[54px] w-[54px] rounded-full" />
              <div className="flex-1">
                <div className="skeleton h-3.5 w-full rounded-full" />
                <div className="skeleton mt-2 h-3.5 w-2/3 rounded-full" />
                <div className="skeleton mt-3 h-5 w-24 rounded-full" />
              </div>
            </div>
            <div className="skeleton mt-4 h-6 w-28 rounded-full" />
            <div className="skeleton mt-4 h-10 w-full rounded-lg" />
          </li>
        ))}
      </ul>
    </div>
  );
}
