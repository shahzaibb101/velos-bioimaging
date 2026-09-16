import { ReactNode, ElementType } from "react";

/** The 1524px content column with responsive gutters. */
export default function Container({
  children, className = "", as: Tag = "div",
}: { children: ReactNode; className?: string; as?: ElementType }) {
  return (
    <Tag
      className={className}
      style={{
        width: "100%",
        maxWidth: "calc(var(--container-max) + 2 * var(--container-padding))",
        marginInline: "auto",
        paddingInline: "var(--container-padding)",
      }}
    >
      {children}
    </Tag>
  );
}
