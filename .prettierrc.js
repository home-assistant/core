/** @type {import("prettier").Config} */
module.exports = {
  overrides: [
    {
      files: ["./homeassistant/components/**/manifest.json"],
      options: {
        plugins: [require.resolve("prettier-plugin-sort-json")],
        jsonRecursiveSort: true,
        // domain and name should stay at the top
        jsonSortOrder: JSON.stringify({
          domain: null,
          name: null,
          [/.*/]: "numeric",
        }),
      },
    },
  ],
};
