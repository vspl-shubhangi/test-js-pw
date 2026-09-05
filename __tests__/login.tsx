import React, { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");

    if (!email || !password) {
      setError("Please fill in all fields.");
      return;
    }

    console.log("Logging in with:", { email, password, rememberMe });
  };

  return (
    <main
      style={{ maxWidth: 420, margin: "40px auto", fontFamily: "sans-serif" }}
    >
      <h1>Login</h1>
      <form onSubmit={handleSubmit} aria-label="login form">
        <div>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            aria-invalid={Boolean(error && !email)}
          />
        </div>

        <div>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            aria-invalid={Boolean(error && !password)}
          />
        </div>

        <label>
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
          />
          Remember me
        </label>

        {error ? <p role="alert">{error}</p> : null}

        <button type="submit">Log in</button>
      </form>
    </main>
  );
}

describe("LoginPage", () => {
  it("renders the login form", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: /login/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log in/i })).toBeInTheDocument();
  });

  it("shows validation error when required fields are missing", () => {
    render(<LoginPage />);

    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Please fill in all fields.",
    );
  });
});
