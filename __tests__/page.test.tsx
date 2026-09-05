import React from "react";
import { render, screen } from "@testing-library/react";
import Home from "../src/app/page";

describe("Home page", () => {
  it("renders title and body text", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /Welcome to Next\.js CI\/CD/i,
    );
    expect(
      screen.getByText(/minimal Next\.js App Router example/i),
    ).toBeInTheDocument();
  });
});
